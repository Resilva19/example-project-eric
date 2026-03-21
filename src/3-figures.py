# Setup ------------------------------------------------------------------------

# Load Libraries [i.e., packages]
# pip install python-dotenv pandas pyreadstat matplotlib seaborn statsmodels
#
# Unlike R's pacman::p_load, Python does not auto-install missing packages.
# Run the line above in your terminal once to install all dependencies.

import os
import numpy as np
import pandas as pd
import pyreadstat
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import statsmodels.api as sm
from dotenv import load_dotenv


# Load environment variables from .env file (see script 1 for detailed comments)
load_dotenv(".env")
data_dir = os.getenv("DATA_DIR")

# If the above is too complicated and you don't have coauthors you can just set
# data_dir manually by commenting out the two lines above and using:
# data_dir = "D:/Dropbox/example-project"


# Read in the data from the previous step --------------------------------------

# Read in the winsorized data.
# pyreadstat.read_dta() returns a tuple: (DataFrame, metadata).
# This is the Python equivalent of haven::read_dta().
regdata, meta = pyreadstat.read_dta(f"{data_dir}/regdata-R.dta")
regdata = regdata[["gvkey", "datadate", "calyear", "roa", "roa_lead_1",
                   "loss", "at", "mve", "rd", "FF12", "ff12num"]]


# Losses by Industry -----------------------------------------------------------

# Compute the percentage of loss observations within each FF12 industry.
# Equivalent to R's group_by(FF12) |> summarize(pct_loss = sum(loss)/n())
fig_data = (
    regdata
    .groupby("FF12")["loss"]
    .mean()  # mean of a 0/1 loss indicator = fraction of losses
    .reset_index()
    .rename(columns={"loss": "pct_loss"})
    # Sort ascending so the horizontal bar chart reads like R's fct_reorder()
    .sort_values("pct_loss")
)

fig, ax = plt.subplots(figsize=(7, 6))
ax.barh(fig_data["FF12"], fig_data["pct_loss"],
        color="#0051ba")  # Kansas Blue: https://brand.ku.edu/guidelines/design/color
ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
ax.set_xlabel("Freq. of Losses")
ax.set_ylabel("Fama-French Industry")
# Use a serif font to match R's theme_bw(base_family = "serif")
plt.rcParams["font.family"] = "serif"
plt.tight_layout()

# Look at it in Python
plt.show()

# For LaTeX output, save as PDF
fig.savefig(f"{data_dir}/output/ff12_fig.pdf", bbox_inches="tight")

# For Word output, save as PNG
fig.savefig(f"{data_dir}/output/ff12_fig.png", dpi=150, bbox_inches="tight",
            figsize=(4.2, 3.6))

plt.close()


# Losses by Size Quintile Over Time --------------------------------------------

figdata = regdata.copy()

# Create size quintiles within each calyear.
# pandas qcut is the equivalent of ntile(mve, 5) in R's dplyr.
# rank(method="first") breaks ties consistently, matching ntile behavior.
figdata["size_qnt"] = (
    figdata.groupby("calyear")["mve"]
    .transform(lambda x: pd.qcut(x.rank(method="first"), 5,
                                 labels=["1", "2", "3", "4", "5"]))
)

fig_data2 = (
    figdata
    .groupby(["calyear", "size_qnt"])["loss"]
    .mean()
    .reset_index()
    .rename(columns={"loss": "pct_loss"})
)

# Line styles to distinguish quintiles (matches R's scale_linetype_discrete)
linestyles = ["-", "--", "-.", ":", (0, (3, 1, 1, 1))]
colors = plt.cm.tab10.colors

fig, ax = plt.subplots(figsize=(7, 6))
for i, (qnt, grp) in enumerate(fig_data2.groupby("size_qnt")):
    grp = grp.sort_values("calyear")
    ax.plot(grp["calyear"], grp["pct_loss"],
            marker="o", linestyle=linestyles[i % len(linestyles)],
            color=colors[i], label=f"Size Quintile {qnt}")

ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
ax.set_xlabel("Year")
ax.set_ylabel("Freq. of Losses")
ax.set_xticks(range(1970, 2026, 5))
# Give the color and linetype scales the same legend name so they merge,
# matching R's scale_color_discrete + scale_linetype_discrete with same name.
ax.legend(title="Size Quintile")
plt.tight_layout()

# Look at it in Python
plt.show()

# For LaTeX
fig.savefig(f"{data_dir}/output/size_year.pdf", bbox_inches="tight")

# For Word
fig.savefig(f"{data_dir}/output/size_year.png", dpi=150, bbox_inches="tight")

plt.close()


# Correlation Matrix Plot ------------------------------------------------------

# Rename columns to match the variable labels used in the paper.
# In R, the corrplot uses LaTeX-style names; here we use plain text.
corrdata = regdata.rename(columns={
    "roa_lead_1": "ROA_{t+1}",
    "roa":        "ROA_t",
    "loss":       "LOSS",
    "rd":         "R&D",
    "at":         "TA",
    "mve":        "SIZE",
})[["ROA_{t+1}", "ROA_t", "LOSS", "R&D", "TA", "SIZE"]]

correlation = corrdata.corr()

# Use a red-white-blue diverging colormap to match R's
# colorRampPalette(c('red', 'white', 'blue'))
cmap = sns.diverging_palette(10, 240, as_cmap=True)

fig, ax = plt.subplots(figsize=(7, 6))
sns.heatmap(correlation,
            annot=True,
            fmt=".2f",
            cmap=cmap,
            center=0,
            square=True,
            linewidths=0.5,
            annot_kws={"size": 9},
            ax=ax)
plt.tight_layout()

fig.savefig(f"{data_dir}/output/corr_fig.pdf", bbox_inches="tight")

plt.close()


# Annual Regressions with Confidence Bands ------------------------------------

# Bonus example just for fun.
#
# Run OLS regressions of roa_lead_1 ~ roa for each (year, loss) group,
# then plot the coefficient on roa over time with 95% confidence bands.
#
# This is the Python equivalent of R's nest_by(calyear, loss) |>
# mutate(fit = list(lm(...))) |> reframe(broom::tidy(fit, conf.int = TRUE)).
#
# Note: statsmodels OLS is the standard Python equivalent of R's lm().
# can also use this setup to do Fama-Macbeth regressions, etc.

results = []
for (calyear, loss), grp in regdata.groupby(["calyear", "loss"]):
    if len(grp) < 3:
        continue
    y = grp["roa_lead_1"].dropna()
    X = sm.add_constant(grp.loc[y.index, "roa"])
    try:
        fit = sm.OLS(y, X).fit()
        ci = fit.conf_int()
        results.append({
            "calyear":   calyear,
            "loss":      loss,
            "estimate":  fit.params["roa"],
            "conf.low":  ci.loc["roa", 0],
            "conf.high": ci.loc["roa", 1],
        })
    except Exception:
        pass

figdata = pd.DataFrame(results)

fig, ax = plt.subplots(figsize=(7, 6))
colors = {0: "steelblue", 1: "darkorange"}

for loss_val, grp in figdata.groupby("loss"):
    grp = grp.sort_values("calyear")
    # Shaded confidence band (grey fill, matching R's geom_ribbon with fill="grey80")
    ax.fill_between(grp["calyear"], grp["conf.low"], grp["conf.high"],
                    alpha=0.3, color="grey80" if "grey80" in plt.colormaps
                    else "lightgrey")
    # Coefficient line with points
    ax.plot(grp["calyear"], grp["estimate"],
            marker="o", color=colors[loss_val], label=f"loss={int(loss_val)}")

ax.set_xlabel("Year")
ax.set_ylabel("Coefficient Estimate (ROA persistence)")
ax.legend(title="Loss")
plt.tight_layout()

# Look at it in Python
plt.show()

# For LaTeX
fig.savefig(f"{data_dir}/output/coef_year.pdf", bbox_inches="tight")

# For Word
fig.savefig(f"{data_dir}/output/coef_year.png", dpi=150, bbox_inches="tight")

plt.close()
