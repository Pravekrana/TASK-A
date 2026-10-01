from pathlib import Path
from streamlit.testing.v1 import AppTest
from vireo.pipeline import run

def test_app_load_filter_and_review(tmp_path):
    run('demo',tmp_path,cache=False)
    at=AppTest.from_file('app.py',default_timeout=20)
    at.run()
    at.sidebar.text_input[1].set_value(str(tmp_path)).run()
    assert not at.exception
    assert '4,000.00' in at.metric[0].value
    at.multiselect[1].set_value(['GW-OTHER']).run()
    assert not at.exception
    # Synthetic decision only, stored under pytest's temporary output folder.
    next(i for i in at.text_input if i.label=='Reviewer name or initials').set_value('TEST reviewer')
    at.text_area[0].set_value('Synthetic fixture decision; no client review performed.')
    next(b for b in at.button if b.label=='Save locally').click().run()
    assert not at.exception
    assert (tmp_path/'reviews'/'decisions.jsonl').exists()
