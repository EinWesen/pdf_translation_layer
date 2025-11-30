# PDF manipulation scripts
These some small scripts, mainly for my personal use.  But maybe someone may find them useful as a start off point.

## translate_cmd - PDF Translation Layer
### Use case
I guess there are tons of PDF translators or even readers with AI supported. 

However there were soem nitpicks i had with then:
- Since Translations are not perrfect i wanted the ability to switch between the translation and the original when reading
- I don't like to send data to an external entity
- And doing something with AI locally just seemed like fun ;)

### The solution
This script extracts the texts blocks form a PDF file, and writes the translation (collected from an LLM) as a new layer on top of the original text.
That way one can use a viewer with layer support to toggle between the two versions.

### How to use
True to form documentaion is lacking, and I stell need to put in some work here. 😅

## reorganize_pdf_gui - Merge, split, and reorder pages
### Use case
Sometimes i find myself having to scan pages, that have texts on both sides. Which lead leads to multiple files, containing some pages. While where are a lot of tools out there to merge/split PDFs or reorder pages i haven't found one that does everything in one go. This this is why i greated this basic gui to combine page from multiple files, and reorder them at the same time.

## Acknowlegements
I took the idea to just add the translation as a new layer to the PDF, and the initial code even, from another great project:
https://github.com/davideuler/pdf-translator-for-human
It has similiar ideas, but more of a interactive focus.

But none of them would have been possible without the great PyMuPDF library: https://github.com/pymupdf/PyMuPDF
