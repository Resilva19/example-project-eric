# Setup ------------------------------------------------------------------------

# Load Libraries [i.e., packages]
# pip install python-dotenv pandas pyreadstat pyfixest scipy tabulate
#
# Unlike R's pacman::p_load, Python does not auto-install missing packages.
# Run the line above in your terminal once to install all dependencies.
#
# Key package equivalents:
#   R fixest::feols     -> Python pyfixest (pip install pyfixest)
#   R modelsummary      -> manual table building + tabulate for LaTeX output
#   R kableExtra / tt   -> tabulate with latex_booktabs format
#   R formattable       -> f-string number formatting

import os
import numpy as np
import pandas as pd
import pyreadstat
from dotenv import load_dotenv
from scipy import stats
import pyfixest as pf
from tabulate import tabulate


# Load environment variables from .env file (see script 1 for detailed comments)
load_dotenv(".env")
data_dir = os.getenv("DATA_DIR")

# If the above is too complicated and you don't have coauthors you can just set
# data_dir manually by commenting out the two lines above and using:
# data_dir = "D:/Dropbox/example-project"


# Read in the data from the previous step --------------------------------------

# Read in the winsorized data.
# I found there are not many firms in the 60s so I am just going to start at 1970.
# pyreadstat.read_dta() is the Python equivalent of haven::read_dta().
regdata, meta = pyreadstat.read_dta(f"{data_dir}/regdata-R.dta")
regdata = regdata[["gvkey", "datadate", "calyear", "roa", "roa_lead_1",
                   "loss", "at", "mve", "rd", "FF12", "ff12num"]]

# Variable label map for display in tables.
# This is the Python equivalent of sjlabelled::var_labels() + label_to_colnames().
# We use LaTeX math notation consistent with the R version.
var_labels = {
    "roa_lead_1": "$ROA_{t+1}$",
    "roa":        "$ROA_t$",
    "loss":       "$LOSS$",
    "rd":         "$R\\&D$",
    "at":         "$TA$",
    "mve":        "$SIZE$",
}


# Observations by Decade -------------------------------------------------------

# Goal: show how to export a basic summary table to LaTeX.
# We group by decade using a function, matching R's case_when() approach.

def assign_decade(year):
    """Map a calendar year to its decade bin label."""
    if 1970 <= year <= 1979:
        return "1970 - 1979"
    elif 1980 <= year <= 1989:
        return "1980 - 1989"
    elif 1990 <= year <= 1999:
        return "1990 - 1999"
    elif 2000 <= year <= 2009:
        return "2000 - 2009"
    elif 2010 <= year <= 2019:
        return "2010 - 2019"
    elif year >= 2020:
        return "2020 - 2022"

regdata["Year"] = regdata["calyear"].apply(assign_decade)

# Within each decade, count observations and compute loss percentage
table1 = (
    regdata
    .groupby("Year")
    .apply(lambda g: pd.Series({
        "Total Firms": f"{len(g):,}",
        "Loss Firms":  f"{int(g['loss'].sum()):,}",
        "Pct. Losses": f"{g['loss'].mean():.2%}",
    }))
    .reset_index()
)

# Add a total row
totalrow = pd.DataFrame([{
    "Year":        "Total",
    "Total Firms": f"{len(regdata):,}",
    "Loss Firms":  f"{int(regdata['loss'].sum()):,}",
    "Pct. Losses": f"{regdata['loss'].mean():.2%}",
}])

# Bind together the decade rows and the total row
table1 = pd.concat([table1, totalrow], ignore_index=True)

# Look at the dataframe
print(table1.to_string(index=False))

# Output to LaTeX using tabulate with "latex_booktabs" format.
# This is the Python equivalent of kableExtra::kbl(..., booktabs = T).
latex_table1 = tabulate(
    table1,
    headers=table1.columns,
    tablefmt="latex_booktabs",
    showindex=False,
)

with open(f"{data_dir}/output/freqtable-py.tex", "w") as f:
    f.write(latex_table1)

# You can also cut and paste the output below directly into Overleaf.
print(latex_table1)


# Table 2: Descriptive Stats ---------------------------------------------------

# Other interesting Python data summary packages:
#   pandas describe()
#   great_tables (gt equivalent)
#   tableone

# Select variables and apply LaTeX labels
descripdata = regdata[["roa_lead_1", "roa", "loss", "rd", "at", "mve"]].rename(
    columns=var_labels
)

# Formatting helpers -----------------------------------------------------------

# Format numbers with commas and specified decimal places.
# This is the Python equivalent of formattable::comma(x, digits=3).
def fmt_num(x, digits=3):
    if pd.isna(x):
        return ""
    return f"{x:,.{digits}f}"

# Count non-missing observations, formatted with no decimals.
# This is the Python equivalent of the custom NN() function in the R script.
def count_n(x):
    return f"{x.count():,.0f}"


# Compute descriptive statistics for each variable
def desc_stats_latex(col):
    """Return formatted descriptive stats for one column."""
    x = col.dropna()
    return pd.Series({
        "N":      count_n(col),
        "Mean":   fmt_num(x.mean()),
        "SD":     fmt_num(x.std()),
        "Min":    fmt_num(x.min()),
        "P25":    fmt_num(x.quantile(0.25)),
        "Median": fmt_num(x.median()),
        "P75":    fmt_num(x.quantile(0.75)),
        "Max":    fmt_num(x.max()),
    })

descrip_stats = descripdata.apply(desc_stats_latex).T.reset_index().rename(
    columns={"index": " "}
)

# Save to LaTeX
# use escape=False so the LaTeX variable names (with $...$) pass through
latex_table2 = tabulate(
    descrip_stats,
    headers=descrip_stats.columns,
    tablefmt="latex_booktabs",
    showindex=False,
)

with open(f"{data_dir}/output/descrip-py.tex", "w") as f:
    f.write(latex_table2)

# Here we save to a tex file. You can also remove the write and copy the
# printed output from the console directly into Overleaf.
print(latex_table2)


# Table 3: Correlation Matrix --------------------------------------------------

# Compute Pearson correlations (upper diagonal) and Spearman (lower diagonal).
# This matches R's datasummary_correlation(method = "pearspear").
pearson  = descripdata.corr(method="pearson")
spearman = descripdata.corr(method="spearman")

# Build combined matrix: Pearson above diagonal, Spearman below diagonal
corrmatrix = pd.DataFrame(index=pearson.index, columns=pearson.columns, dtype=object)
n = len(corrmatrix)
for i in range(n):
    for j in range(n):
        if i == j:
            corrmatrix.iloc[i, j] = ""
        elif i < j:
            corrmatrix.iloc[i, j] = f"{pearson.iloc[i, j]:.3f}"
        else:
            corrmatrix.iloc[i, j] = f"{spearman.iloc[i, j]:.3f}"

corrmatrix.insert(0, " ", corrmatrix.index)
corrmatrix = corrmatrix.reset_index(drop=True)

# Save to LaTeX
latex_table3 = tabulate(
    corrmatrix,
    headers=corrmatrix.columns,
    tablefmt="latex_booktabs",
    showindex=False,
)

with open(f"{data_dir}/output/corrtable-py.tex", "w") as f:
    f.write(latex_table3)

print(latex_table3)


# Table 4: Regression Table ----------------------------------------------------

# Run the five models using pyfixest (the Python equivalent of R's fixest::feols).
# pyfixest uses R-like formula syntax: "y ~ x | fe1 + fe2"
# The labels you give each model will appear in the column headings.
#
# fixef.rm="both" (remove singletons) is not directly available in pyfixest,
# but singletons are handled implicitly by the demeaning algorithm.

# Cluster standard errors by gvkey and calyear (two-way clustering).
# Equivalent to R's vcov = ~ gvkey + calyear.
vcov_spec = {"CRV1": "gvkey + calyear"}

models = {
    "Base":          pf.feols("roa_lead_1 ~ roa",
                              data=regdata, vcov=vcov_spec),
    "No FE":         pf.feols("roa_lead_1 ~ roa * loss",
                              data=regdata, vcov=vcov_spec),
    "Year FE":       pf.feols("roa_lead_1 ~ roa * loss | calyear",
                              data=regdata, vcov=vcov_spec),
    "Two-Way FE":    pf.feols("roa_lead_1 ~ roa * loss | calyear + gvkey",
                              data=regdata, vcov=vcov_spec),
    "With Controls": pf.feols("roa_lead_1 ~ roa * loss + at + rd + mve | calyear + gvkey",
                              data=regdata, vcov=vcov_spec),
}

# Coefficient map: controls which coefficients appear and their LaTeX labels.
# Coefficients not listed here are silently dropped from the table.
# This is the Python equivalent of R's coef_map argument in modelsummary.
# Note how this also labels the interaction term.
coef_map = {
    "roa":      "$ROA_{t}$",
    "loss":     "$LOSS$",
    "roa:loss": "$ROA_{t} \\times LOSS$",
}

# Significance stars. Equivalent to
# R's stars = c('\\sym{*}' = .1, '\\sym{**}' = .05, '\\sym{***}' = .01)
def add_stars(pval):
    if pval < 0.01:
        return "\\sym{***}"
    elif pval < 0.05:
        return "\\sym{**}"
    elif pval < 0.1:
        return "\\sym{*}"
    return ""

def extract_model_results(model, model_name):
    """Extract formatted coefficient estimates and t-stats from a pyfixest model."""
    params = model.coef()
    tvals  = model.tstat()
    pvals  = model.pvalue()
    rows = []
    for coef_name, label in coef_map.items():
        if coef_name in params.index:
            est   = params[coef_name]
            tstat = tvals[coef_name]
            stars = add_stars(pvals[coef_name])
            rows.append({"term": label,         model_name: f"{est:.3f}{stars}"})
            rows.append({"term": "",             model_name: f"({tstat:.2f})"})
        else:
            rows.append({"term": label,          model_name: ""})
            rows.append({"term": "",             model_name: ""})
    return rows

# Build the coefficient block of the table (first model sets the row structure)
first_name, first_model = next(iter(models.items()))
table_rows = extract_model_results(first_model, first_name)

for name, m in list(models.items())[1:]:
    model_rows = extract_model_results(m, name)
    for i, row in enumerate(model_rows):
        table_rows[i][name] = row[name]

t4_coefs = pd.DataFrame(table_rows)

# Goodness-of-fit rows
def has_fe(model, fe_name):
    """Check whether the model includes a given fixed effect."""
    try:
        return fe_name in model._fixef
    except Exception:
        return False

def has_controls(model):
    """Check whether the model includes control variables."""
    controls = ["at", "rd", "mve"]
    return all(c in model.coef().index for c in controls)

gof_specs = [
    ("Year FE",    lambda m: "X" if has_fe(m, "calyear") else ""),
    ("Firm FE",    lambda m: "X" if has_fe(m, "gvkey") else ""),
    ("Controls",   lambda m: "X" if has_controls(m) else ""),
    # Format N as \multicolumn{1}{c}{...} to center it in the LaTeX table,
    # matching R's custom nobs_fmt function
    ("N",          lambda m: f"\\multicolumn{{1}}{{c}}{{{m.nobs:,.0f}}}"),
    ("$R^2$",      lambda m: f"{m.rsquared:.3f}"),
    ("$R^2$ Within", lambda m: f"{m.rsquared_within:.3f}" if hasattr(m, 'rsquared_within') else ""),
]

gof_rows = []
for gof_label, getter in gof_specs:
    row = {"term": gof_label}
    for name, m in models.items():
        row[name] = getter(m)
    gof_rows.append(row)

t4_gof = pd.DataFrame(gof_rows)

# Combine coefficient rows and goodness-of-fit rows
col_order = ["term"] + list(models.keys())
t4 = pd.concat([t4_coefs, t4_gof])[col_order].reset_index(drop=True)

# Preview the output
print(t4.to_string(index=False))

# Output to LaTeX with booktabs formatting.
# This is the Python equivalent of modelsummary(..., output = "path/to/file.tex",
#   escape = F, booktabs = T).
latex_table4 = tabulate(
    t4,
    headers=t4.columns,
    tablefmt="latex_booktabs",
    showindex=False,
)

with open(f"{data_dir}/output/regression-py.tex", "w") as f:
    f.write(latex_table4)

print(latex_table4)

# Optional: if you prefer to manually add heading and FE rows outside this
# script, you can copy the LaTeX output into Overleaf and edit it there.
# The .tex file is read directly by the LaTeX template on Overleaf.
