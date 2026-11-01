import pytest, uuid

template_bundle_name = "example.json"
template_bundle_uuid4 = uuid.uuid4().hex
template_trace_uuid4 = uuid.uuid4().hex


@pytest.fixture
def sample_bundle_uuid():
    return template_bundle_uuid4

@pytest.fixture
def sample_bundle_name():
    return template_bundle_name

@pytest.fixture
def sample_trace_uuid():
    return template_trace_uuid4



@pytest.fixture
def empty_bundle_dir(tmp_path):
    return tmp_path

@pytest.fixture
def empty_dict():
    return {}

@pytest.fixture
def bundle_dir(tmp_path):
    (tmp_path / template_bundle_name).write_text("{}")
    return tmp_path

@pytest.fixture
def sample_bundles_dict():
    return {template_bundle_uuid4: template_bundle_name}

@pytest.fixture
def sample_registered_bundles_dict():
    return {template_bundle_name: template_trace_uuid4}

@pytest.fixture
def sample_traces_dict():
    return {    
        template_trace_uuid4: {
            "trace": object(),
            "bundle_name": template_bundle_name,
            "bundle_id": template_bundle_uuid4,
        }
    }

