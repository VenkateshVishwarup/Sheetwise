import json
import duckdb
import pytest


def fixture_profile(tmp_path):
    path=tmp_path/'evaluation.duckdb'
    with duckdb.connect(str(path)) as con:
        con.execute('CREATE TABLE dataset(c0 VARCHAR, c1 BOOLEAN, c2 VARCHAR, c3 VARCHAR)')
        con.executemany('INSERT INTO dataset VALUES (?,?,?,?)',[(('Source A' if i%2 else 'SourceA'),None if i>=200 else i%2==0,'private@example.com','done') for i in range(240)])
        con.execute('CREATE TABLE original AS SELECT CAST(c0 AS VARCHAR) c0, CAST(c1 AS VARCHAR) c1, CAST(c2 AS VARCHAR) c2, CAST(c3 AS VARCHAR) c3 FROM dataset')
    return {'id':'11111111-1111-4111-8111-111111111111','rowCount':240,'databasePath':str(path),'columns':[
        {'key':'c0','name':'channel','type':'category','queryable':True,'sensitive':False,'distinctCount':2},
        {'key':'c1','name':'converted','type':'boolean','queryable':True,'sensitive':False,'distinctCount':2},
        {'key':'c2','name':'email','type':'category','queryable':False,'sensitive':True,'distinctCount':1},
        {'key':'c3','name':'lead_status','type':'category','queryable':True,'sensitive':False,'distinctCount':1}]}


def definition(**kwargs):
    return {'targetKey':'c1','featureKeys':['c0'],'purpose':'snapshot','positiveMeaning':'Converted at export','negativeMeaning':'Not converted at export','labelsConfirmed':True,'featuresConfirmed':True,'categoriesReviewed':False,**kwargs}


def test_readiness_preserves_unknowns_and_blocks_ambiguous_categories(tmp_path):
    from backend.evaluation import run_evaluation
    r=run_evaluation(fixture_profile(tmp_path),definition())
    assert (r['knownRows'],r['unknownRows'],r['positiveRows'],r['negativeRows'])==(200,40,100,100)
    assert not r['ready']
    assert any(i['code']=='CATEGORY_COLLISION' for i in r['issues'])
    assert 'Source A' not in json.dumps(r) and 'private@example.com' not in json.dumps(r)


def test_forbids_protected_target_and_outcome_features(tmp_path):
    from backend.evaluation import run_evaluation
    p=fixture_profile(tmp_path)
    for features in [['c1'],['c2'],['c3'],['c0','c0']]:
        with pytest.raises(ValueError):
            run_evaluation(p,definition(featureKeys=features))


def test_future_and_unconfirmed_definitions_cannot_run(tmp_path):
    from backend.evaluation import run_evaluation
    p=fixture_profile(tmp_path)
    for changes in [{'purpose':'future'},{'labelsConfirmed':False},{'featuresConfirmed':False}]:
        d=definition(categoriesReviewed=True,**changes)
        assert not run_evaluation(p,d)['ready']
        with pytest.raises(ValueError):run_evaluation(p,d,evaluate=True)


def test_evaluation_is_reproducible_and_excludes_unknown_outcomes(tmp_path):
    from backend.evaluation import run_evaluation
    p=fixture_profile(tmp_path);d=definition(categoriesReviewed=True)
    a=run_evaluation(p,d,evaluate=True);b=run_evaluation(p,d,evaluate=True)
    assert a['trainRows']+a['testRows']==200
    assert a['testRows']==50
    assert a['models']==b['models']
    assert a['models'][0]['rocAuc']==.5
    assert a['models'][1]['rocAuc']>.9
    assert 'rows' not in a and 'predictions' not in a
    assert a['definition']['negativeMeaning']=='Not converted at export'


def test_metrics_handle_ties_and_probabilities():
    from backend.evaluation import score_predictions
    m=score_predictions([0,1,0,1],[.5,.5,.5,.5])
    assert m=={'rocAuc':.5,'averagePrecision':.5,'brier':.25}
    assert score_predictions([0,1],[0,1])=={'rocAuc':1.,'averagePrecision':1.,'brier':0.}


def test_small_minority_blocks_evaluation(tmp_path):
    from backend.evaluation import run_evaluation
    p=fixture_profile(tmp_path)
    with duckdb.connect(p['databasePath']) as c:c.execute("UPDATE original SET c1='false' WHERE rowid>10")
    r=run_evaluation(p,definition(categoriesReviewed=True))
    assert not r['ready'] and any(x['code']=='TOO_FEW_OUTCOMES' for x in r['issues'])


def test_worker_is_killable_and_does_not_inherit_credentials(tmp_path,monkeypatch):
    from backend import evaluation
    p=fixture_profile(tmp_path)
    monkeypatch.setenv('OPENAI_API_KEY','never-pass-this-test-secret')
    original=evaluation.subprocess.Popen
    seen=[]
    def launch(*args,**kwargs):
        seen.append(kwargs['env'])
        return original(*args,**kwargs)
    monkeypatch.setattr(evaluation.subprocess,'Popen',launch)
    assert evaluation.run_evaluation(p,definition(categoriesReviewed=True))['ready']
    assert all('OPENAI_API_KEY' not in env for env in seen)
    monkeypatch.setattr(evaluation,'TIMEOUT',0)
    with pytest.raises(ValueError,match='exceeded'):
        evaluation.run_evaluation(p,definition(categoriesReviewed=True))


def test_imported_case_variants_are_checked_and_preserved(tmp_path):
    from backend.ingest import ingest_file
    from backend.evaluation import run_evaluation
    path=tmp_path/'case.csv'
    path.write_text('channel,converted\n'+''.join(('Paid,true\n' if i%2 else 'paid,false\n') for i in range(200)))
    root=tmp_path/'data';root.mkdir()
    profile=ingest_file(path,'case.csv',root)
    readiness=run_evaluation(profile,definition())
    assert readiness['features'][0]['collisionGroups']==1
    assert not readiness['ready']
    run=run_evaluation(profile,definition(categoriesReviewed=True),evaluate=True)
    assert run['models'][1]['rocAuc']==1


@pytest.mark.parametrize('name',['isConverted','leadStatus','isQualified','appointmentBooked','conversion','APIConversion'])
def test_common_outcome_proxies_are_excluded(name):
    from backend.evaluation import eligible_feature
    assert not eligible_feature({'name':name,'type':'category','queryable':True,'sensitive':False,'distinctCount':2})
