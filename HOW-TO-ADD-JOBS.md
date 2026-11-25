# How to add jobs to Rep Installs

The live map reads a list of jobs from a spreadsheet in this repository. You can add jobs yourself in the browser, or send an AccuLynx export and have the list rebuilt from that.

The site is public (same as the live page), so only put the usual fields: job number, company, homeowner name, house number and street, city (used to place the pin, never shown on the map), date, roof type, insurance company or Retail, and optional notes. Do not add anything extra.

A job whose name or notes mention a lien is left off the map. The job number KNX-10408 is also left off, on purpose.

## Add or edit jobs on github.com (about two minutes)

1. On your phone or computer, open this repository and go to the file **data/jobs.csv**.
   Direct link: https://github.com/biggerduckman/rep-installs/blob/main/data/jobs.csv
2. Tap or click the **pencil** (Edit) in the top right of the file.
3. Scroll to the bottom and add a new line. Keep the columns in this order, separated by commas. If a value has a comma in it, wrap that value in double quotes.

   Columns:

   `job_id, company, homeowner, address, city, date, roof_type, carrier_or_retail, lat, lng, notes`

   - **job_id** — a unique job number, for example `GMET-2001` or `KNX-2001`
   - **company** — `Gold Medal Roofing` or `Perimeter Roofing` (you can also type `Gold Medal` or `Perimeter`)
   - **homeowner** — the name to show on the pin (leave blank if there isn't one)
   - **address** — house number and street only, for example `3506 Orlando St` (no city)
   - **city** — city, state, and ZIP, for example `Knoxville, TN 37917`. Used only to place the pin. It is not shown on the map.
   - **date** — completed date as `YYYY-MM-DD`, for example `2026-11-24` (optional)
   - **roof_type** — optional
   - **carrier_or_retail** — the insurance company, or `Retail`
   - **lat** and **lng** — leave these blank if you do not know them. The rebuild will fill them in from the address.
   - **notes** — optional. Do not put lien information here if you want the job on the map.

   Example (leave lat and lng empty so the pin is looked up automatically):

   `GMET-2001,Gold Medal Roofing,Jane Smith,3506 Orlando St,"Knoxville, TN 37917",2026-11-24,,Retail,,`

4. At the bottom, choose **Commit changes** (save). You can keep the suggested message or type your own.
5. Wait about two minutes, then open https://biggerduckman.github.io/rep-installs/ and pull to refresh. The new pin should be there.

### Or upload a full spreadsheet

If it is easier to edit the file in Excel or Numbers:

1. From the **data/jobs.csv** page, download the current file first. This is important — uploading a file that only has the new jobs would replace the whole list and remove everyone else.
2. Add your new rows to that downloaded file and save it as CSV, still named `jobs.csv`.
3. Go to the **data** folder, choose **Add file → Upload files**, and upload your `jobs.csv` so it replaces the existing one.
4. Commit, then wait about two minutes and refresh the live map.

## Have an AccuLynx export rebuilt for you

If you have a new AccuLynx jobs export instead, send that file and ask for the list to be rebuilt. That path uses the same spreadsheet and the same rules, so the map stays in agreement either way.
