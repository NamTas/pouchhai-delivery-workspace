# Data separation

## My orders

Starts empty. `data/reviews.sqlite3` is created locally and stores user-entered/imported order records, source corrections and follow-up history. No user-order database or test-created orders are shipped. Use `import_template.csv` or the UI template download. Back up the SQLite file with the app stopped.

## Demo data

`demo_orders.csv` contains 120 transformed records from **Olist**, Brazilian E-Commerce Public Dataset:
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

License: **CC BY-NC-SA 4.0** — https://creativecommons.org/licenses/by-nc-sa/4.0/

Retain attribution, license and transformations when redistributing the demo data. The live application code is separately MIT-licensed; the Olist data retains its non-commercial/share-alike terms.

The demo joins order dates with city/state. It excludes customer identifiers, payment values and review narratives. Events after 2018-08-31 23:59:59 are masked. The selected sample includes 40 overdue-at-cutoff, 60 delivered-late and 20 on-time records. Selection, hashes and caveats are in `provenance.json`. This is not a representative performance sample or Bangladeshi merchant data.

Demo records and demonstration follow-ups stay in their own workspace. User-created live records are not copied into demo files. Test fixtures use temporary databases outside the delivered data folder.
