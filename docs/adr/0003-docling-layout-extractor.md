# Price lists are converted to text by Docling, with the pdfplumber reader for two-column pages

Plain PDF-to-text separates table labels from their values (BBVA, N26, DKB, Hanseatic), so the LLM sees fees it cannot
attach to anything. We compared Docling, PyMuPDF4LLM, MinerU and our pdfplumber reader on all 16 catalog PDFs (November
2026, throwaway script): numbers kept from the PDF's text layer, tables on the known bad pages, runtime, license.

- **pdfplumber reader** (ours): keeps every number, 9 s for all 16; tables lose their labels on BBVA p.3, N26 p.1/p.3–4,
  DKB p.1–2. The only one that reads HVB's two-column label/value pages (p.1–2, 4–9) with each fee next to its label.
- **Docling** (MIT): clean Markdown tables on every known bad page; drops no fee number (only headers and footers,
  which we export too); about 5 min on CPU for all 16, plus a model download; on HVB's column pages values become
  headings detached from their labels; ING p.5 (securities, no card fees) comes out as one table cell.
- **PyMuPDF4LLM** (AGPL): good tables on BBVA, DKB and Hanseatic, but loses fees on HVB ("9,90 EUR" becomes "990 EUR",
  2,90 EUR missing) and C24 (1,99 EUR).
- **MinerU** (AGPL): table structure, but deletes word spaces in BBVA's tables ("BareinzahlungbeiEinzelhandelspartnern"),
  which breaks quotes; 5.5 hours for all 16 on CPU.

No candidate passed alone, so ingest uses Docling for every page except one Docling finds no table on and our reader
splits into two text columns; those pages keep the pdfplumber reader. Docling is the `ingest` install extra: the app
answers from the fees file and never converts. The converted text is committed beside each PDF (`<id>.md`) so review
shows what the model read, and a price list whose text lacks a number from the PDF's text layer is flagged and not
extracted.
