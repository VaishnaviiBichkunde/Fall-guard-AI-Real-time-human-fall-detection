from streamlit.testing.v1 import AppTest


def test_fragment_can_update_a_slot_reserved_on_initial_render():
    app = AppTest.from_string(
        """
import streamlit as st

slot = st.empty()
slot.empty()

@st.fragment(run_every=0.1)
def render():
    slot.markdown("Live content")

render()
"""
    ).run()

    assert not app.exception
