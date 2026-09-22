"""Generate the component-first, example-rich OpenAPI 3.0 contract."""
from pathlib import Path
import yaml

schemas={}
def ref(name): return {'$ref':f'#/components/schemas/{name}'}
def scalar(name,kind,example,description,**constraints):
    schemas[name]={'type':kind,'description':description,'example':example,**constraints}
def array(name,item,example,description,max_items=500):
    schemas[name]={'type':'array','items':ref(item),'maxItems':max_items,'description':description,'example':example}
def obj(name,properties,example,description,required=None):
    schemas[name]={'type':'object','description':description,'properties':{k:ref(v) for k,v in properties.items()},'required':list(properties) if required is None else required,'additionalProperties':False,'example':example}

uid='8c6bc148-166a-4cdd-b3d8-21609201b05f'
scalar('ResourceId','string',uid,'An opaque identifier assigned by this workspace.',format='uuid',minLength=36,maxLength=36,pattern='^[0-9a-f-]{36}$')
scalar('Text','string','Users by region','A human-readable value. Uploaded values are data, never executable instructions.',maxLength=2000)
scalar('ShortText','string','User journey','A short label shown in the application.',minLength=1,maxLength=160)
scalar('Question','string','How many records are in this dataset?','An aggregate question about the selected dataset.',minLength=1,maxLength=2000)
scalar('Password','string','a-long-random-workspace-password','The server-configured shared workspace password.',minLength=1,maxLength=256,format='password')
scalar('Boolean','boolean',True,'A true or false value; missing observations are represented separately.')
scalar('Count','integer',4628,'A nonnegative count.',minimum=0,maximum=2_000_000_000)
scalar('Number','number',42.5,'A finite numerical value.')
scalar('Percentage','number',94.2,'A percentage between zero and one hundred.',minimum=0,maximum=100)
scalar('CreatedAt','string','2026-09-08T18:00:00+00:00','UTC timestamp when the record was created.',format='date-time')
scalar('Sql','string','SELECT COUNT(*) AS records FROM dataset','Validated DuckDB SELECT statement for this dataset.',maxLength=12000)
scalar('ColumnKey','string','c1','A safe SQL identifier independent of the uploaded header.',pattern='^c[0-9]{1,3}$',minLength=2,maxLength=4)
scalar('ColumnType','string','category','The conservative inferred analytical type.',enum=['category','boolean','number','date','text','identifier'])
scalar('PrivacyReason','string','personal','Why a column is protected or restricted.',enum=['','identifier','personal','unstructured'])
scalar('AnswerKind','string','answer','An executed answer or a clarification that ran no SQL.',enum=['answer','clarification'])
scalar('WireVersion','string','v0.9.1','Pinned A2UI protocol version.',enum=['v0.9.1'])
scalar('CatalogId','string','https://sheetwise.local/catalogs/analytics/v1','Only the application-owned analytics catalog is accepted.',enum=['https://sheetwise.local/catalogs/analytics/v1'])
scalar('ComponentType','string','BarChart','An approved analytics component.',enum=['Metric','BarChart','LineChart','DataTable','Notice'])
scalar('JsonPointer','string','/rows','A path into the surface data model.',pattern='^/.*$',maxLength=160)
scalar('File','string','(binary CSV or XLSX file)','Uploaded UTF-8 CSV or XLSX content, at most 100 MB.',format='binary')
scalar('NullableText','string',None,'An optional label; null means unavailable.',nullable=True,maxLength=2000)
scalar('NullableSql','string',None,'SQL is null when asking for clarification.',nullable=True,maxLength=12000)
scalar('Offset','integer',0,'Number of preview records to skip.',minimum=0,maximum=2_000_000)
scalar('PreviewLimit','integer',25,'Maximum records returned in a preview page.',minimum=1,maximum=100)
scalar('AttemptCount','integer',1,'Generation attempts, including up to two repairs. Zero means clarification.',minimum=0,maximum=3)
scalar('ComponentId','string','root','Component identifier. Every surface has a root component.',minLength=1,maxLength=100,pattern='^[A-Za-z0-9_-]+$')
schemas['Cell']={'description':'A scalar result value. Null represents an unknown value.','nullable':True,'example':193,'oneOf':[ref('Text'),ref('Number'),ref('Boolean')]}
array('Strings','Text',['West','East'],'A bounded list of display strings.')
array('ResultRow','Cell',['west',240],'Ordered scalar values for one result row.')
array('ResultRows','ResultRow',[['west',240],['east',160]],'Up to 200 executed result rows.',200)
obj('DistributionItem',{'label':'Text','count':'Count'},{'label':'hot','count':485},'Count of records with a normalized category value; Unknown represents blanks.')
array('Distribution','DistributionItem',[{'label':'hot','count':485}],'Top 12 categories by record count.',12)
column_example={'key':'c1','name':'lead_status','type':'category','coverage':95.8,'distinctCount':4,'missingCount':193,'sensitive':False,'queryable':True,'privacyReason':'','distribution':[{'label':'hot','count':485}]}
column_props={'key':'ColumnKey','name':'ShortText','type':'ColumnType','coverage':'Percentage','distinctCount':'Count','missingCount':'Count','sensitive':'Boolean','queryable':'Boolean','privacyReason':'PrivacyReason','distribution':'Distribution','trueCount':'Count','falseCount':'Count','min':'Number','max':'Number','mean':'Number','sum':'Number'}
obj('Column',column_props,column_example,'An inferred column profile. Numeric and boolean statistics are present only when relevant.',list(column_example))
array('Columns','Column',[column_example],'All retained column profiles.')
obj('DataBinding',{'path':'JsonPointer'},{'path':'/rows'},'Resolve a component value from the executed surface data model.')
schemas['BoundValue']={'description':'A literal scalar or a reference to surface data.','example':{'path':'/value'},'oneOf':[ref('DataBinding'),ref('Cell')]}
obj('UiComponent',{'id':'ComponentId','component':'ComponentType','title':'Text','subtitle':'Text','value':'BoundValue','detail':'BoundValue','rows':'DataBinding','labelKey':'Text','valueKey':'Text','columns':'Strings','text':'BoundValue'}, {'id':'root','component':'Metric','title':'Records','subtitle':'','value':{'path':'/value'},'detail':{'path':'/detail'}},'Properties are validated against the named analytics component catalog. Only relevant properties are supplied.',['id','component','title','subtitle'])
array('UiComponents','UiComponent',[schemas['UiComponent']['example']],'Components to create or replace on a surface.',50)
obj('CreateSurface',{'surfaceId':'ResourceId','catalogId':'CatalogId'},{'surfaceId':uid,'catalogId':schemas['CatalogId']['example']},'Create a surface using the fixed analytics catalog.')
obj('UpdateComponents',{'surfaceId':'ResourceId','components':'UiComponents'},{'surfaceId':uid,'components':[schemas['UiComponent']['example']]},'Create or replace declarative components.')
schemas['DisplayRow']={'type':'object','description':'A result object keyed by the executed result column labels.','additionalProperties':ref('Cell'),'example':{'region':'west','records':240}}
array('DisplayRows','DisplayRow',[{'region':'west','records':240}],'Executed chart or table rows.',200)
obj('SurfaceData',{'value':'Cell','detail':'Text','rows':'DisplayRows','labelKey':'Text','valueKey':'Text','columns':'Strings','text':'Text'}, {'value':4628,'detail':'All records'},'Executed data for the selected component; only relevant properties are present.',[])
obj('UpdateDataModel',{'surfaceId':'ResourceId','value':'SurfaceData'},{'surfaceId':uid,'value':{'value':4628,'detail':'All records'}},'Replace the surface data model with verified values.')
obj('CreateSurfaceMessage',{'version':'WireVersion','createSurface':'CreateSurface'},{'version':'v0.9.1','createSurface':schemas['CreateSurface']['example']},'A2UI surface creation message.')
obj('UpdateComponentsMessage',{'version':'WireVersion','updateComponents':'UpdateComponents'},{'version':'v0.9.1','updateComponents':schemas['UpdateComponents']['example']},'A2UI component update message.')
obj('UpdateDataModelMessage',{'version':'WireVersion','updateDataModel':'UpdateDataModel'},{'version':'v0.9.1','updateDataModel':schemas['UpdateDataModel']['example']},'A2UI data binding update message.')
schemas['A2uiMessage']={'description':'One approved v0.9.1 lifecycle message.','example':schemas['CreateSurfaceMessage']['example'],'oneOf':[ref('CreateSurfaceMessage'),ref('UpdateComponentsMessage'),ref('UpdateDataModelMessage')]}
array('A2uiMessages','A2uiMessage',[schemas['CreateSurfaceMessage']['example'],schemas['UpdateComponentsMessage']['example'],schemas['UpdateDataModelMessage']['example']],'Ordered creation, component and data messages.',100)
obj('DashboardCard',{'id':'Text','title':'Text','source':'Text','sql':'Sql','messages':'A2uiMessages'},{'id':'c1','title':'Lead status','source':'lead_status','sql':'SELECT c1, COUNT(*) FROM dataset GROUP BY c1','messages':schemas['A2uiMessages']['example']},'An automatically generated card with source and SQL provenance.')
array('Dashboard','DashboardCard',[schemas['DashboardCard']['example']],'Deterministic charts generated from all dataset records.',10)
dataset_props={'id':'ResourceId','name':'ShortText','filename':'Text','rowCount':'Count','inputColumnCount':'Count','columnCount':'Count','excludedCount':'Count','sizeBytes':'Count','createdAt':'CreatedAt','sheetName':'NullableText','isDemo':'Boolean'}
dataset_example={'id':uid,'name':'User journey','filename':'journey.csv','rowCount':4628,'inputColumnCount':134,'columnCount':133,'excludedCount':1,'sizeBytes':12888387,'createdAt':schemas['CreatedAt']['example'],'sheetName':None}
obj('DatasetSummary',dataset_props,dataset_example,'An uploaded dataset without column or dashboard details.',list(dataset_example))
obj('Dataset',{**dataset_props,'columns':'Columns','warnings':'Strings','dashboard':'Dashboard'},{**dataset_example,'columns':[column_example],'warnings':['Missing values remain unknown.'],'dashboard':schemas['Dashboard']['example']},'The complete dataset profile and its default dashboard.',list(dataset_example)+['columns','warnings','dashboard'])
array('DatasetList','DatasetSummary',[dataset_example],'Datasets in this shared workspace, newest first.',10000)
obj('PreviewColumn',{'key':'ColumnKey','name':'Text','type':'ColumnType','sensitive':'Boolean'},{'key':'c1','name':'lead_status','type':'category','sensitive':False},'Source-preview column metadata.')
array('PreviewColumns','PreviewColumn',[schemas['PreviewColumn']['example']],'Preview column definitions.')
schemas['PreviewRow']={'type':'object','description':'Original values keyed by safe column IDs; protected values display bullets.','additionalProperties':ref('Cell'),'example':{'c0':'••••','c1':'Hot'}}
array('PreviewRows','PreviewRow',[{'c0':'••••','c1':'Hot'}],'One preview page, with personal values masked.',100)
obj('Preview',{'columns':'PreviewColumns','rows':'PreviewRows','total':'Count','offset':'Offset'},{'columns':schemas['PreviewColumns']['example'],'rows':schemas['PreviewRows']['example'],'total':4628,'offset':0},'A masked preview of original data; no AI service is involved.')
obj('QueryResult',{'columns':'Strings','rows':'ResultRows','truncated':'Boolean','elapsedMs':'Count'},{'columns':['region','records'],'rows':[['west',240],['east',160]],'truncated':False,'elapsedMs':90},'Values returned by validated SQL execution in the isolated worker.')
schemas['NullableResult']={**schemas['QueryResult'],'nullable':True,'example':None}
answer_example={'id':uid,'question':'How many records are in this dataset?','kind':'answer','title':'Records','summary':'Records: 4,628.','choices':[],'sql':'SELECT COUNT(*) AS records FROM dataset','result':{'columns':['records'],'rows':[[4628]],'truncated':False,'elapsedMs':90},'messages':schemas['A2uiMessages']['example'],'pinned':False,'attempts':1,'plan':'Count all records.','createdAt':schemas['CreatedAt']['example']}
obj('Answer',{'id':'ResourceId','question':'Question','kind':'AnswerKind','title':'Text','summary':'Text','choices':'Strings','sql':'NullableSql','result':'NullableResult','messages':'A2uiMessages','pinned':'Boolean','attempts':'AttemptCount','plan':'Text','createdAt':'CreatedAt'},answer_example,'An executed answer or clarification, persisted for follow-up questions and optional pinning.')
array('Answers','Answer',[answer_example],'Conversation answers in creation order.',10000)
obj('WorkspaceStatus',{'authenticated':'Boolean','passwordRequired':'Boolean','aiConfigured':'Boolean','model':'ShortText','maxUploadBytes':'Count','localMode':'Boolean','directUploads':'Boolean'},{'authenticated':True,'passwordRequired':False,'aiConfigured':True,'model':'gpt-5.6-sol','maxUploadBytes':104857600,'localMode':True,'directUploads':False},'Workspace availability. aiConfigured reports key presence, not account credit availability.')
obj('SessionResult',{'authenticated':'Boolean'},{'authenticated':True},'Whether the workspace session is authenticated.')
obj('LoginRequest',{'password':'Password'},{'password':schemas['Password']['example']},'Authenticate using the shared workspace password.')
obj('ChatRequest',{'question':'Question'},{'question':schemas['Question']['example']},'Ask an aggregate question about the selected dataset.')
obj('PinRequest',{'answerId':'ResourceId','pinned':'Boolean'},{'answerId':uid,'pinned':True},'Save or unsave an existing answer. pinned defaults to true.',['answerId'])
obj('PinResult',{'answerId':'ResourceId','pinned':'Boolean'},{'answerId':uid,'pinned':True},'The persisted pin state.')
obj('UploadRequest',{'file':'File','sheetName':'ShortText'},{'file':'(binary CSV content)','sheetName':'Users'},'Multipart upload. Omit sheetName to import the first XLSX worksheet.',['file'])
scalar('ErrorCode','string','INVALID_REQUEST','Stable error classification.',enum=['INVALID_REQUEST','UNAUTHORIZED','NOT_FOUND','INTERNAL_ERROR','SERVICE_UNAVAILABLE','ORIGIN_REJECTED','HOST_REJECTED','FILE_TOO_LARGE','IMPORT_BUSY','CHAT_BUSY'])
obj('Error',{'code':'ErrorCode','message':'Text','requestId':'Text'},{'code':'INVALID_REQUEST','message':'Choose a valid dataset.','requestId':uid},'A standardized error without raw source values or provider credentials.')
obj('ErrorResponse',{'error':'Error'}, {'error':schemas['Error']['example']},'Error envelope used by all API operations.')

for component in schemas.values():
    if component.get('required') == []:
        component.pop('required')


scalar('UploadPath','string','uploads/'+uid+'.csv','An immutable upload pathname inside the private workspace Blob store.',minLength=48,maxLength=49,pattern=r'^uploads/[0-9a-f-]{36}\.(csv|xlsx)$')
scalar('UploadFilename','string','leads.csv','Original CSV/XLSX filename; used to select the parser.',minLength=1,maxLength=160,pattern=r'^.+\.([cC][sS][vV]|[xX][lL][sS][xX])$')
scalar('OptionalSheet','string',None,'Optional worksheet; null selects the first worksheet.',nullable=True,maxLength=160)
obj('CloudImportRequest',{'pathname':'UploadPath','filename':'UploadFilename','sheetName':'OptionalSheet'},{'pathname':'uploads/'+uid+'.csv','filename':'leads.csv','sheetName':None},'Import a completed direct upload, persist its analytical database, and remove the source after successful commit. Retry with the same pathname after a transient failure.',['pathname','filename'])
scalar('BlobEventType','string','blob.generate-client-token','Official Blob SDK event type.',enum=['blob.generate-client-token','blob.upload-completed'])
scalar('UploadToken','string','(short-lived upload token)','A server-issued token restricted to one private upload path and 100 MB.',minLength=1,maxLength=16000)
obj('BlobFile',{'url':'Text','pathname':'Text','contentType':'Text','contentDisposition':'Text','downloadUrl':'Text','etag':'Text'},{'url':'https://store.private.blob.vercel-storage.com/uploads/example.csv','pathname':'uploads/example.csv','contentType':'application/octet-stream'},'Provider metadata for a completed private upload.',['url','pathname','contentType'])
obj('BlobUploadPayload',{'pathname':'UploadPath','clientPayload':'NullableText','multipart':'Boolean','blob':'BlobFile','tokenPayload':'NullableText'},{'pathname':'uploads/'+uid+'.csv','clientPayload':None,'multipart':True},'SDK token request or signed provider completion payload; the fields depend on the event.',[])
obj('BlobUploadRequest',{'type':'BlobEventType','payload':'BlobUploadPayload'},{'type':'blob.generate-client-token','payload':schemas['BlobUploadPayload']['example']},'Official Blob upload handshake. Token generation requires a workspace session. Completion callbacks are verified by the Blob SDK.')
obj('BlobUploadResponse',{'type':'BlobEventType','clientToken':'UploadToken','response':'ShortText'},{'type':'blob.generate-client-token','clientToken':'(short-lived upload token)'},'Upload authorization or completion acknowledgment returned by the official SDK.',['type'])

scalar('EvaluationPurpose','string','snapshot','Snapshot compares recorded status. Future intent is recognized but blocked until dated history is available.',enum=['snapshot','future'])
scalar('OutcomeMeaning','string','Converted at the time of export','The data owner’s definition of an observed boolean label.',minLength=3,maxLength=200)
array('EvaluationFeatureKeys','ColumnKey',['c0'],'One to twelve unique, permitted categorical or boolean inputs.',12)
schemas['EvaluationFeatureKeys'].update(minItems=1,uniqueItems=True)
definition_example={'targetKey':'c1','featureKeys':['c0'],'purpose':'snapshot','positiveMeaning':'Converted at export','negativeMeaning':'Not converted at export','labelsConfirmed':True,'featuresConfirmed':True,'categoriesReviewed':False}
obj('EvaluationDefinition',{'targetKey':'ColumnKey','featureKeys':'EvaluationFeatureKeys','purpose':'EvaluationPurpose','positiveMeaning':'OutcomeMeaning','negativeMeaning':'OutcomeMeaning','labelsConfirmed':'Boolean','featuresConfirmed':'Boolean','categoriesReviewed':'Boolean'},definition_example,'Define an outcome and acknowledge its meaning and input suitability. Confirmations default to false; category acknowledgment never merges values.',['targetKey','featureKeys','positiveMeaning','negativeMeaning'])
scalar('ReadinessCode','string','CATEGORY_COLLISION','A stable readiness issue classification.',enum=['HISTORY_REQUIRED','CONFIRM_LABELS','CONFIRM_INPUTS','TOO_FEW_OUTCOMES','TOO_MANY_ROWS','CLASS_IMBALANCE','LOW_LABEL_COVERAGE','TOO_MANY_CATEGORIES','LOW_VARIATION','LONG_VALUE','CATEGORY_COLLISION','COVERAGE_SHIFT','NO_VARYING_INPUTS'])
scalar('ReadinessSeverity','string','blocker','Blockers prevent evaluation; warnings remain visible in the saved report.',enum=['blocker','warning'])
schemas['OptionalColumnKey']={**schemas['ColumnKey'],'nullable':True,'example':None}
schemas['OptionalCoverage']={**schemas['Percentage'],'nullable':True,'example':None,'description':'Coverage among unknown outcomes; null if there are no unknown outcomes.'}
obj('ReadinessIssue',{'code':'ReadinessCode','message':'Text','severity':'ReadinessSeverity','columnKey':'OptionalColumnKey'},{'code':'CATEGORY_COLLISION','message':'Verify category names that differ only by spacing.','severity':'blocker','columnKey':'c0'},'A data-quality or definition issue. Raw category values are never included.')
array('ReadinessIssues','ReadinessIssue',[schemas['ReadinessIssue']['example']],'Checks and cautions for this exact definition.',100)
feature_example={'key':'c0','name':'channel','knownCoverage':98.0,'unknownCoverage':60.0,'distinctKnown':4,'collisionGroups':1}
obj('ReadinessFeature',{'key':'ColumnKey','name':'ShortText','knownCoverage':'Percentage','unknownCoverage':'OptionalCoverage','distinctKnown':'Count','collisionGroups':'Count'},feature_example,'Aggregate input coverage and category naming checks; no values or individual scores.')
array('ReadinessFeatures','ReadinessFeature',[feature_example],'The selected input checks.',12)
readiness_example={'ready':False,'totalRows':240,'knownRows':200,'unknownRows':40,'positiveRows':100,'negativeRows':100,'targetName':'converted','features':[feature_example],'issues':schemas['ReadinessIssues']['example']}
obj('OutcomeReadiness',{'ready':'Boolean','totalRows':'Count','knownRows':'Count','unknownRows':'Count','positiveRows':'Count','negativeRows':'Count','targetName':'ShortText','features':'ReadinessFeatures','issues':'ReadinessIssues'},readiness_example,'Eligibility for a pilot evaluation, recomputed from the stored dataset. Ready never means validated for production prediction.')
scalar('EvaluationMetric','number',0.71,'A finite metric in [0,1]. ROC AUC and average precision are higher-is-better; Brier error is lower-is-better.',minimum=0,maximum=1)
scalar('EvaluationMethod','string','Categorical naive Bayes','Fixed pilot model; no tuning or external AI calls.',enum=['Prevalence reference','Categorical naive Bayes'])
obj('EvaluationModel',{'name':'EvaluationMethod','rocAuc':'EvaluationMetric','averagePrecision':'EvaluationMetric','brier':'EvaluationMetric'},{'name':'Categorical naive Bayes','rocAuc':0.71,'averagePrecision':0.65,'brier':0.2},'Aggregate held-out metrics, with tie-aware ranking and precision calculations.')
array('EvaluationModels','EvaluationModel',[schemas['EvaluationModel']['example']],'Reference and categorical model evaluated on the same holdout.',2)
scalar('EvaluationSeed','integer',42,'Fixed seed for the stratified 75/25 split.',enum=[42])
scalar('EvaluationVersion','string','snapshot-categorical-v1','Reproducible evaluation algorithm identifier.',enum=['snapshot-categorical-v1'])
run_example={'id':uid,'datasetId':uid,'createdAt':schemas['CreatedAt']['example'],'definition':definition_example,'readiness':{**readiness_example,'ready':True,'issues':[]},'trainRows':150,'testRows':50,'testPositiveRows':25,'seed':42,'algorithmVersion':'snapshot-categorical-v1','models':schemas['EvaluationModels']['example'],'limitations':['Recorded status only; not a future forecast.']}
obj('EvaluationRun',{'id':'ResourceId','datasetId':'ResourceId','createdAt':'CreatedAt','definition':'EvaluationDefinition','readiness':'OutcomeReadiness','trainRows':'Count','testRows':'Count','testPositiveRows':'Count','seed':'EvaluationSeed','algorithmVersion':'EvaluationVersion','models':'EvaluationModels','limitations':'Strings'},run_example,'Immutable completed evaluation with definitions, checks and aggregate results. No row predictions are stored or returned.')
array('EvaluationRuns','EvaluationRun',[run_example],'Latest twenty completed evaluations for the selected dataset, newest first.',20)
schemas['ErrorCode']['enum'].append('EVALUATION_BUSY')

paths={}
errors={'400':'Bad Request — invalid fields, unsupported file or rejected query.','401':'Unauthorized — a valid workspace session is required.','403':'Forbidden — untrusted host or cross-origin write.','404':'Not Found — dataset or answer does not exist.','413':'Payload Too Large — request or file exceeds its limit.','429':'Too Many Requests — import or analysis capacity is busy.','500':'Internal Error — the request could not be completed.','503':'Service Unavailable — AI configuration, credits or provider availability prevents analysis.'}
def endpoint(path,method,operation,summary,response,body=None,success='200',params=None,public=False,multipart=False):
    op={'operationId':operation,'summary':summary,'description':summary+' All records belong to the single authenticated internal workspace.','responses':{success:{'description':'Created successfully.' if success=='201' else 'Request completed.','content':{'application/json':{'schema':ref(response)}}},**{code:{'description':desc,'content':{'application/json':{'schema':ref('ErrorResponse')}}} for code,desc in errors.items()}}}
    if public:op['security']=[]
    if '{dataset_id}' in path:op['parameters']=[{'name':'dataset_id','in':'path','required':True,'description':'The dataset selected in the workspace.','schema':ref('ResourceId'),'example':uid}]
    if params:op.setdefault('parameters',[]).extend(params)
    if body:op['requestBody']={'required':True,'content':{'multipart/form-data' if multipart else 'application/json':{'schema':ref(body)}}}
    paths.setdefault(path,{})[method]=op
endpoint('/api/status','get','getWorkspaceStatus','Read sign-in and AI configuration status.','WorkspaceStatus',public=True)
endpoint('/api/session','post','createWorkspaceSession','Create an HttpOnly workspace session.','SessionResult','LoginRequest',public=True)
endpoint('/api/session','delete','deleteWorkspaceSession','Clear this browser’s workspace session cookie.','SessionResult',public=True)
endpoint('/api/datasets','get','listDatasets','List uploaded datasets.','DatasetList')
endpoint('/api/datasets','post','uploadDataset','Import and profile a CSV or XLSX file.','Dataset','UploadRequest','201',multipart=True)
endpoint('/api/imports','post','importCloudUpload','Import a completed private cloud upload.','Dataset','CloudImportRequest','201')
endpoint('/api/blob-upload','post','authorizeCloudUpload','Authorize a private direct upload or acknowledge a signed completion callback.','BlobUploadResponse','BlobUploadRequest')
endpoint('/api/demo','post','createDemoDataset','Create a clearly labeled synthetic demonstration dataset.','Dataset',success='201')
endpoint('/api/datasets/{dataset_id}','get','getDataset','Read a dataset profile and its default dashboard.','Dataset')
endpoint('/api/datasets/{dataset_id}/preview','get','getDatasetPreview','Preview masked original values.','Preview',params=[{'name':name,'in':'query','description':schemas[kind]['description'],'schema':ref(kind),'example':schemas[kind]['example']} for name,kind in [('offset','Offset'),('limit','PreviewLimit')]])
endpoint('/api/datasets/{dataset_id}/answers','get','listAnswers','Read the dataset conversation history.','Answers')
endpoint('/api/datasets/{dataset_id}/chat','post','answerDatasetQuestion','Plan, validate and execute an analytical question.','Answer','ChatRequest')
endpoint('/api/datasets/{dataset_id}/pins','get','listPinnedAnswers','List saved answers for this dataset.','Answers')
endpoint('/api/datasets/{dataset_id}/pins','post','setAnswerPinned','Save or unsave an existing answer.','PinResult','PinRequest')
endpoint('/api/datasets/{dataset_id}/readiness','post','checkOutcomeReadiness','Check data readiness for a recorded binary outcome.','OutcomeReadiness','EvaluationDefinition')
endpoint('/api/datasets/{dataset_id}/evaluations','post','evaluateRecordedOutcome','Evaluate and save a bounded binary-status comparison.','EvaluationRun','EvaluationDefinition','201')
endpoint('/api/datasets/{dataset_id}/evaluations','get','listOutcomeEvaluations','Read the latest twenty saved outcome evaluations.','EvaluationRuns')
endpoint('/api/openapi.yaml','get','getApiSpecification','Download this API contract.','Text')
paths['/api/openapi.yaml']['get']['responses']['200']['content']={'application/yaml':{'schema':ref('Text')}}
paths['/api/session']['post']['responses']['200']['headers']={'Set-Cookie':{'description':'HttpOnly, SameSite=Strict session cookie; Secure when COOKIE_SECURE=true.','schema':ref('Text'),'example':'sheetwise_session=(signed session); HttpOnly; SameSite=Strict; Path=/'}}
spec={'openapi':'3.0.3','info':{'title':'Sheetwise API','version':'2.0.0','description':'Private spreadsheet analytics. One shared internal workspace; all analytical database paths remain server-side. Schemas and examples are defined in components.'},'servers':[{'url':'http://127.0.0.1:8000','description':'Local development; use your HTTPS internal origin for deployment.'}],'security':[{'WorkspaceSession':[]}],'paths':paths,'components':{'securitySchemes':{'WorkspaceSession':{'type':'apiKey','in':'cookie','name':'sheetwise_session','description':'Signed workspace session. Loopback-only local mode can omit this cookie.'}},'schemas':schemas}}
for component in schemas.values():
    if component.get('required') == []:
        component.pop('required')
out=Path(__file__).resolve().parents[1]/'docs/openapi.yaml'
out.write_text(yaml.safe_dump(spec,sort_keys=False,allow_unicode=True))
print(f'Generated {len(paths)} paths and {len(schemas)} component schemas.')
