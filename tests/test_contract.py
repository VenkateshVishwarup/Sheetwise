from pathlib import Path
import yaml
from openapi_spec_validator import validate


def test_contract_is_valid_and_uses_components_and_examples():
    contract=yaml.safe_load((Path(__file__).parents[1]/'docs/openapi.yaml').read_text())
    validate(contract)
    assert contract['openapi']=='3.0.3'
    assert all('example' in schema for schema in contract['components']['schemas'].values())
    for path in contract['paths'].values():
        for operation in path.values():
            assert {'400','401','500'}<=operation['responses'].keys()
            assert any(c in operation['responses'] for c in ('200','201'))
            for response in operation['responses'].values():
                for content in response.get('content',{}).values():
                    assert '$ref' in content['schema']
            for parameter in operation.get('parameters',[]):
                assert 'example' in parameter and '$ref' in parameter['schema']
