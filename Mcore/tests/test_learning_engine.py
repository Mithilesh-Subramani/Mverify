import pytest
from mcore.learning.engine import LearningEngine

def test_experience_requires_evidence(tmp_path):
    engine=LearningEngine(tmp_path/'learning.db')
    with pytest.raises(ValueError):
        engine.record_experience('compile', {'dut':'x'}, {'prediction':'pass'}, {'result':'fail'}, {})

def test_lesson_requires_human_review_and_consent(tmp_path):
    engine=LearningEngine(tmp_path/'learning.db')
    exp=engine.record_experience('compile', {'dut':'x'}, {'prediction':'pass'},
        {'result':'fail'}, {'log':'VCS error'})
    lesson=engine.propose_lesson(exp['id'], 'Check package compile order before module files.',
        'systemverilog', {'log':'VCS error'})
    with pytest.raises(ValueError):
        engine.review_lesson(lesson['id'], approve=True, consent=False)
    result=engine.review_lesson(lesson['id'], approve=True, consent=True, reviewer='engineer')
    assert result['status']=='validated'
    assert engine.status()['validated_consented_lessons']==1

def test_reject_lesson(tmp_path):
    engine=LearningEngine(tmp_path/'learning.db')
    exp=engine.record_experience('sim', {'dut':'x'}, {}, {'result':'fail'}, {'log':'e'})
    lesson=engine.propose_lesson(exp['id'], 'Unverified claim', 'general', {'log':'e'})
    assert engine.review_lesson(lesson['id'], approve=False)['status']=='rejected'

def test_evaluation_needs_comparable_baseline(tmp_path):
    engine=LearningEngine(tmp_path/'learning.db')
    no_base=engine.record_evaluation('regression', {'pass_rate':0.9})
    assert no_base['decision']=='not_proven'
    improved=engine.record_evaluation('regression', {'pass_rate':0.95,'error_rate':0.02},
        baseline={'pass_rate':0.9,'error_rate':0.04})
    assert improved['decision']=='improved'

def test_no_model_weight_claim(tmp_path):
    status=LearningEngine(tmp_path/'learning.db').status()
    assert status['model_weights_updated'] is False
