# Setup ------------------------------------------------------------------------

# Load Libraries [i.e., packages]
# pip install python-dotenv pandas pyarrow pyreadstat matplotlib scipy
#
# Unlike R's pacman::p_load, Python does not auto-install missing packages.
# Run the line above in your terminal once to install all dependencies.

import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyreadstat
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv

# Import helper functions from utils.py.
# This is the Python equivalent of source("src/utils.R").
# Unlike R's source(), Python imports are explicit and scoped.
import sys
sys.path.insert(0, "src")
from utils import (assign_FF12, assign_FF12_num,
                   assign_FF49, assign_FF49_num,
                   winsorize_x, write_parquet)


# Load environment variables from .env file (see script 1 for detailed comments)
load_dotenv(".env")
data_dir = os.getenv("DATA_DIR")

# Sample period parameters.
# We set these as module-level variables, equivalent to R's global parameters.
beg_year = 1970
end_year = 2022

# If the above is too complicated and you don't have coauthors you can just set
# data_dir manually by commenting out the two lines above and using:
# data_dir = "D:/Dropbox/example-project"


# Read in the data from the previous step --------------------------------------

# Let's work with the parquet version.
# pd.read_parquet() is the Python equivalent of arrow::read_parquet() in R.
# Note: if you chose to collect your raw data in SAS or Stata, these could
# easily be read in using pyreadstat.read_dta() or pyreadstat.read_sas7bdat().
data1 = pd.read_parquet(f"{data_dir}/raw-data-py.parquet")


# Some quick peeks at the data -------------------------------------------------

# Calling print() on a DataFrame shows a preview, similar to just calling
# the name of a tibble in R.
print(data1)

# pandas info() is similar to glimpse() in R
data1.info()

# pandas describe() is similar to summary() in R
print(data1.describe())


# Manipulate a few variables ---------------------------------------------------

# Many of the below steps could be combined into one. They also could have been
# done on the WRDS server. I separate them here for teaching purposes.

# Filter based on the global sample period parameters.
# This is the Python equivalent of filter(calyear >= beg_year, calyear <= end_year).
data2 = data1[
    (data1["calyear"] >= beg_year) &
    (data1["calyear"] <= end_year)
].copy()

# We scale by total assets (at), so we set a minimum at to avoid small
# denominators. Equivalent to R's filter(at >= 10).
data2 = data2[data2["at"] >= 10].copy()

# Assign Fama-French industry classifications using our helper functions.
# These call numpy.select() under the hood (equivalent to R's case_when),
# so they work efficiently on the whole column at once.
data2["FF12"]    = assign_FF12(data2["sic4"])
data2["ff12num"] = assign_FF12_num(data2["sic4"])
data2["FF49"]    = assign_FF49(data2["sic4"])
data2["ff49num"] = assign_FF49_num(data2["sic4"])

# Code a loss dummy (1 if earnings < 0, 0 otherwise).
# I like 1/0 but True/False is also fine.
# This is the Python equivalent of if_else(e < 0, 1, 0).
data2["loss"] = (data2["e"] < 0).astype(int)

# Scale earnings (e) by ending total assets.
# FSA purists would probably use average total assets, but just an example.
data2["roa"] = data2["e"] / data2["at"]

# Scale R&D by ending total assets
data2["rd"] = data2["xrd"] / data2["at"]

# Let's do an earnings persistence regression with lead earnings as y.
# For each firm (gvkey) we need the next period's earnings.
# First make sure the data is sorted properly.
data2 = data2.sort_values(["gvkey", "datadate"])

# Then group by firm (gvkey) so the shift only looks at the next observation
# for the same firm. This is the Python equivalent of
# group_by(gvkey) |> mutate(roa_lead_1 = lead(roa, 1L), ...) |> ungroup().
data2["roa_lead_1"]     = data2.groupby("gvkey")["roa"].shift(-1)
data2["datadate_lead_1"] = data2.groupby("gvkey")["datadate"].shift(-1)

# Check to make sure there are no gaps or fiscal year changes.
# We require that the lead observation is exactly one year later.
# Equivalent to R's filter(month(datadate_lead_1) == month(datadate),
#                          year(datadate_lead_1) == year(datadate) + 1)
data2["datadate"]        = pd.to_datetime(data2["datadate"])
data2["datadate_lead_1"] = pd.to_datetime(data2["datadate_lead_1"])

data2 = data2[
    (data2["datadate_lead_1"].dt.month == data2["datadate"].dt.month) &
    (data2["datadate_lead_1"].dt.year  == data2["datadate"].dt.year + 1)
].copy()

# Filter to require non-missing values for key variables.
# This is the Python equivalent of filter(if_all(c(at, mve, rd, ff12num,
#   starts_with("roa")), ~ !is.na(.x))).
required_cols = ["at", "mve", "rd", "ff12num", "roa", "roa_lead_1"]
data2 = data2.dropna(subset=required_cols).copy()


# Play around ------------------------------------------------------------------

# How many observations in each FF12 industry?
# Equivalent to data2 |> group_by(FF12) |> count()
print(data2.groupby("FF12").size().reset_index(name="n"))

# Percentage of losses by industry?
# Equivalent to data2 |> group_by(FF12) |> summarize(pct_loss = sum(loss)/n())
print(
    data2.groupby("FF12")["loss"]
    .mean()
    .reset_index(name="pct_loss")
)

# As a quick figure?
# This is the Python equivalent of the inline ggplot in 2-transform-data.R.
fig_data = (
    data2.groupby("FF12")["loss"]
    .mean()
    .reset_index(name="pct_loss")
    .sort_values("pct_loss")  # sort so bars read sensibly
)

fig, ax = plt.subplots(figsize=(7, 5))
ax.barh(fig_data["FF12"], fig_data["pct_loss"])
ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
ax.set_xlabel("Freq. of Losses")
ax.set_ylabel("Fama-French Industry")
plt.tight_layout()
plt.show()


# Winsorize the data -----------------------------------------------------------

# Check the tail values as an example.
# numpy percentile is the Python equivalent of R's quantile().
print(np.nanpercentile(data2["roa"], [0, 1, 99, 100]))

# Default winsorization: 1% / 99%.
# We apply winsorize_x() to several columns.
# The Python equivalent of mutate(across(c(mve, at, rd, starts_with("roa")),
#   winsorize_x)).
data3 = data2.copy()
for col in ["mve", "at", "rd", "roa", "roa_lead_1"]:
    data3[col] = winsorize_x(data3[col])

# Check the winsorized tail values
print(np.nanpercentile(data3["roa"], [0, 1, 99, 100]))


# Alternate version: winsorize at 2.5% / 97.5%
# Equivalent to mutate(across(..., ~ winsorize_x(.x, cuts = c(0.025, 0.025))))
data3b = data2.copy()
for col in ["rd", "roa", "roa_lead_1"]:
    data3b[col] = winsorize_x(data3b[col], cuts=(0.025, 0.025))

# Check
print(np.nanpercentile(data2["roa"],  [0, 2.5, 97.5, 100]))
print(np.nanpercentile(data3b["roa"], [0, 2.5, 97.5, 100]))


# Save the winsorized data  ----------------------------------------------------

# Save to Stata format for working with coauthors.
# f-strings are the Python equivalent of R's glue() for dynamic file paths.
# pyreadstat.write_dta() is the Python equivalent of haven::write_dta().
pyreadstat.write_dta(data3, f"{data_dir}/regdata-py.dta")
