from scripts.etl.execute_etl import load_pipeline_config
import os

def test_pipeline_config_loads_correctly():
    config = load_pipeline_config()
    
    # Assert main sections exist
    assert "pipeline_stages" in config
    assert "reset_targets" in config
    
    # Assert reset_targets is a list
    assert isinstance(config["reset_targets"], list)
    assert len(config["reset_targets"]) > 0
    
    # Assert pipeline stages structure
    stages = config["pipeline_stages"]
    assert isinstance(stages, list)
    
    for stage in stages:
        assert "name" in stage
        assert "steps" in stage
        assert isinstance(stage["steps"], list)
        
        for step in stage["steps"]:
            assert "phase_id" in step
            assert "template" in step
            
            # The template file must exist
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            template_path = os.path.join(base_dir, "sql", "etl", "dml", step["template"])
            assert os.path.exists(template_path), f"Template file {step['template']} does not exist"
