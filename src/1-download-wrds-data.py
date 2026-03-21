# Setup ------------------------------------------------------------------------

# Load Libraries [i.e., packages]
# pip install python-dotenv keyring sqlalchemy psycopg2-binary pandas
#             pyarrow pyreadstat
#
# Unlike R's pacman::p_load, Python does not auto-install missing packages.
# Run the line above in your terminal once to install all dependencies.

import os
import time
import keyring
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pyreadstat
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# Load environment variables from .env file ------------------------------------

# SHARING CODE WITH COAUTHORS USING .env FILES
#
# A .env file is a simple text file that stores configuration variables like
# file paths. Each line has the format: VARIABLE_NAME=value
#
# WHY USE IT?
# - Your code doesn't contain hardcoded paths specific to your computer
# - Coauthors can run the same code by creating their own .env file
# - Better for sharing code publicly (e.g., journal submissions)
# - The .env file is gitignored so each person has their own local copy
# - Works across R, Python, and Stata using the same .env file
#
# SETUP (one-time):
# 1. Open the .env file in the project root directory
# 2. Change the DATA_DIR path to wherever you want to store data
#    Example: DATA_DIR=D:/Dropbox/example-project
#    Notice the slashes go the other way from Windows!
# 3. Save the file. You should only have to do this once per computer.
#
# It is recommended to not store your data in the Git project folder.
# Github is designed for hosting code, not data.
# I use a separate folder, usually in Dropbox if there is enough space.

load_dotenv(".env")
data_dir = os.getenv("DATA_DIR")

# If the above is too complicated and you don't have coauthors you can just set
# data_dir manually by commenting out the two lines above and using:
# data_dir = "D:/Dropbox/example-project"


# Log into WRDS ----------------------------------------------------------------

# We use the keyring package to securely store your WRDS credentials in your
# operating system's credential store (Windows Credential Manager, macOS
# Keychain, etc.). This is more secure than putting passwords in .env files.
# Note: Do NOT put passwords in .env - use keyring for secrets.
#
# FIRST TIME SETUP - run these lines once in your Python console:
#   import keyring
#   keyring.set_password("wrds", "wrds_user", "your_wrds_username")
#   keyring.set_password("wrds", "wrds_pw",   "your_wrds_password")
# This stores credentials securely in your system's keychain.
# You only need to do this once per computer.
#
# To update stored credentials (e.g., after a password change), just re-run
# the set_password lines above with the new values.

wrds_user = keyring.get_password("wrds", "wrds_user")
wrds_pw   = keyring.get_password("wrds", "wrds_pw")

# SQLAlchemy is the Python equivalent of R's DBI/RPostgres.
# It creates a connection engine to the WRDS PostgreSQL server.
engine = create_engine(
    f"postgresql+psycopg2://{wrds_user}:{wrds_pw}"
    f"@wrds-pgdata.wharton.upenn.edu:9737/wrds",
    connect_args={"sslmode": "require"},
)

# Check that the connection works
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    print("Connected to WRDS:", result.fetchone()[0])


# See a list of tables in a schema ---------------------------------------------
# Just an example to play with the Postgres server

# List all tables in the Compustat (comp) schema
with engine.connect() as conn:
    tables = pd.read_sql(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'comp'
        ORDER BY table_name
        """,
        conn,
    )
    print(tables)
# can replace 'comp' with any schema such as 'crsp', 'ibes', etc.
# schemas on the Postgres server are similar to WRDS SAS libraries


# Download data ----------------------------------------------------------------

# Optional: start a timer to see how long the download takes
# Equivalent to tictoc::tic() / toc() in R
tic = time.time()

# Get some raw Compustat data from funda.
#
# Unlike R's dbplyr (which lazily builds SQL and only downloads on collect()),
# here we write the SQL directly and execute it in one step.
# The result is equivalent -- all filtering and joining happens on the WRDS
# server, and only the final result is transferred to your local machine.

query = """
SELECT
    f.conm,
    f.gvkey,
    f.datadate,
    f.fyear,
    f.fyr,
    f.cusip             AS cstat_cusip,
    f.cik,
    f.tic               AS cstat_ticker,
    f.sich,
    f.ib,
    f.spi,
    f.at,
    f.xrd,
    f.ceq,
    f.sale,
    f.csho,
    f.prcc_f,

    -- From the company header file (equivalent of inner_join with comp.company)
    c.sic,
    c.fic,
    c.gind,

    -- Use historical SIC (sich) when available, otherwise header SIC (sic)
    -- COALESCE is SQL's equivalent of R's coalesce()
    COALESCE(f.sich, c.sic::numeric)                        AS sic4,

    -- Two-digit SIC code: floor(sic4 / 100)
    FLOOR(COALESCE(f.sich, c.sic::numeric) / 100)           AS sic2,

    -- Calendar year alignment: assume a 3-month reporting lag, align to June.
    -- If the fiscal year end month (fyr) is after March, add 1 to the year.
    -- See Hou, Van Dijk, and Zhang (2012 JAE) figure 1 for motivation.
    -- EXTRACT(YEAR FROM ...) is the SQL equivalent of R's sql("extract(year from datadate)")
    CASE
        WHEN f.fyr > 3
        THEN EXTRACT(YEAR FROM f.datadate) + 1
        ELSE EXTRACT(YEAR FROM f.datadate)
    END                                                     AS calyear,

    -- Market value of equity
    f.csho * f.prcc_f                                       AS mve,

    -- Earnings before special items: ib - spi (treating NULL spi as 0)
    f.ib - COALESCE(f.spi, 0)                               AS e,

    -- Replace NULLs with 0 for SPI and XRD (as in R's mutate + coalesce)
    COALESCE(f.spi, 0)                                      AS spi_clean,
    COALESCE(f.xrd, 0)                                      AS xrd_clean

FROM comp.funda f
INNER JOIN comp.company c
    ON f.gvkey = c.gvkey

WHERE
    -- Standard Compustat filters (same as the R filter() call)
    f.indfmt  = 'INDL'
    AND f.datafmt = 'STD'
    AND f.popsrc  = 'D'
    AND f.consol  = 'C'

    -- Filter to fiscal years after 1967 (not much in Compustat before that)
    AND f.fyear > 1967

    -- Filter to US companies only
    AND c.fic = 'USA'
"""

with engine.connect() as conn:
    raw_funda = pd.read_sql(query, conn)

# Stop the timer
toc = time.time()
print(f"Download complete in {toc - tic:.1f} seconds")

# Post-download filter: remove financial (SIC 60-69) and utility (SIC 49) firms.
# These filters reference sic2, which we computed inside SQL above.
# We apply them here in Python (pandas) instead of SQL for clarity,
# mirroring how the R code uses filter() after mutate().
raw_funda = raw_funda[
    ~raw_funda["sic2"].between(60, 69) &
    (raw_funda["sic2"] != 49)
]

# Overwrite spi and xrd with the coalesced (NULL -> 0) versions computed in SQL
# then drop the temporary _clean columns
raw_funda["spi"] = raw_funda["spi_clean"]
raw_funda["xrd"] = raw_funda["xrd_clean"]
raw_funda = raw_funda.drop(columns=["spi_clean", "xrd_clean"])

print(f"Rows after filtering: {len(raw_funda):,}")


# Save the data to disk --------------------------------------------------------

# Saving to Stata format is convenient for working with coauthors.
# f-strings (f"...{variable}...") are Python's equivalent of R's glue().
# Each coauthor can specify their own local data folder in .env.
pyreadstat.write_dta(raw_funda, f"{data_dir}/raw-data-py.dta")
# looks like about 162 MB in the R version; Python output will be similar

# If the data will stay in Python (or R/other modern languages), Parquet is a
# nice open-source columnar file format for data science.
# It is fast, small, and supports metadata.
#
# We use gzip compression at level 5, matching the custom write_parquet()
# function defined in utils.R.
table = pa.Table.from_pandas(raw_funda)
pq.write_table(
    table,
    f"{data_dir}/raw-data-py.parquet",
    compression="gzip",
)
# The parquet file is much smaller than the .dta file (around 32 MB in R).

print("Data saved to disk.")
