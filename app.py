import streamlit as st
import importlib
import traceback

st.set_page_config(page_title="PV & Battery Calculator", layout="wide")
st.title("PV & Battery Calculator - interactive")

st.markdown("Provide yearly PV production and yearly consumption, then run the calculator and show the summary table from `calculator.py`.")

# Import calculator module to read defaults
try:
    import calculator_git
    importlib.reload(calculator_git)
except Exception:
    calculator_git = None

# Get defaults if available
default_pv = None
default_consumption = None
if calculator_git is not None:
    default_pv = getattr(calculator_git, 'yearly_pv_production', None)
    default_consumption = getattr(calculator_git, 'yearly_consumption', None)

col1, col2 = st.columns(2)
with col1:
    yearly_pv_production = st.number_input(
        "Yearly PV production (kWh)",
        min_value=0.0,
        value=float(default_pv) if default_pv is not None else 6000.0,
        step=100.0,
    )
with col2:
    yearly_consumption = st.number_input(
        "Yearly consumption (kWh)",
        min_value=0.0,
        value=float(default_consumption) if default_consumption is not None else 14500.0,
        step=100.0,
    )

run = st.button("Run calculation")

if run:
    if calculator_git is None:
        st.error("Unable to import calculator.py. Fix errors in that file first.")
    else:
        # Inject values and reload module
        try:
            # Set attributes on the module so code can pick them up at import
            setattr(calculator_git, 'yearly_pv_production', yearly_pv_production)
            setattr(calculator_git, 'yearly_consumption', yearly_consumption)
            # Reload the module to re-run top-level calculations using new values
            importlib.reload(calculator_git)

            # Retrieve the summary dataframe
            summary = getattr(calculator_git, 'summary', None)
            if summary is None:
                st.error("`summary` not found in calculator.py after reload. Make sure the script defines `summary` as a pandas DataFrame.")
            else:
                st.success("Calculation finished - showing summary")
                st.dataframe(summary)

                # Download as CSV
                csv = summary.to_csv(index=True).encode('utf-8')
                st.download_button("Download CSV", csv, file_name="summary.csv", mime='text/csv')
        except Exception as e:
            st.error("An error occurred while running calculator.py")
            st.text(traceback.format_exc())
else:
    st.info("Change inputs and click 'Run calculation' to execute the script and show the `summary` table.")

st.markdown("---")
st.markdown("Notes: This app reloads `calculator_git.py` when you press Run. Ensure `calculator_git.py` reads `yearly_pv_production` and `yearly_consumption` as global variables at import time and produces a `summary` pandas DataFrame.")
