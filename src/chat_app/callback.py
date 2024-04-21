import streamlit as st


if __name__ == "__main__":
    if st.query_params.get("code") is None:
        st.error("This page should not be accessed directly.")
        st.stop()
    else:
        loader = """
<style>
  .custom-loader {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 9999;
    width: 100px;
    height: 100px;
    border: 8px solid #f3f3f3;
    border-top: 8px solid #3498db;
    border-radius: 50%;
    animation: spin 2s linear infinite;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
</style>
<div class='custom-loader'></div>
"""
        st.markdown(loader, unsafe_allow_html=True)
