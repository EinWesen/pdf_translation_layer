import fitz  # PyMuPDF
import tkinter as tk
from tkinter import PhotoImage
from tkinter import filedialog as SystemFileDialog
import io
import argparse
import os
from collections.abc import Sequence



# Define a class to store information about each page
class PageItem:
    def __init__(self, page_name:str, page_index:int, doc_ref:fitz.Document, selected:bool=False):
        self.page_scale_matrix:fitz.Matrix = fitz.Matrix(0.4, 0.4)
        self.page_name:str = page_name  # e.g., "Page 1"
        self.page_index:int = page_index  # Actual page index in the PDF
        self.doc_ref:fitz.Document = doc_ref  # Image data (PNG byte stream) for the page preview
        self.selected:bool = selected  # Whether the page is selected (internal state)
    
    def get_page_as_png(self)->io.BytesIO:
        page = self.doc_ref.load_page(self.page_index)
        pix = page.get_pixmap(matrix=self.page_scale_matrix)  # Resize for thumbnail
        return io.BytesIO(pix.tobytes("png"))

class OrganizePdfDialog:
    def _append_page_item(self, page_item:PageItem):
        self.page_items.append(page_item)
        self.page_listbox.insert(tk.END, page_item.page_name)
        self._update_colors(len(self.page_items)-1)

    # Function to load PDF and extract page previews
    def add_pdf(self, pdf_paths:str|Sequence[str])->None:        
        if isinstance(pdf_paths, str) or not isinstance(pdf_paths, Sequence):
             pdf_paths = [pdf_paths]
        
        last_pdf_index = len(pdf_paths)-1
        
        for pdf_index, pdf_path in enumerate(pdf_paths):
            
            with fitz.open(pdf_path) as doc:
            
                filename = os.path.basename(pdf_path)

                if self.main_document is None:
                    self.main_document = fitz.open("pdf", doc.write())

                    for page_num in range(len(doc)):
                        # Create PageItem for each page, including image data
                        page_name = f"{filename} - Page {page_num + 1}"
                        self._append_page_item(PageItem(page_name, page_num, self.main_document, True))

                else:               
                    is_final = 1 if (pdf_index == last_pdf_index) else 0
                    self.main_document.insert_pdf(doc, from_page=0, to_page=-1, start_at=-1, rotate=-1, links=True, annots=True, widgets=True, join_duplicates=False, show_progress=0, final=is_final)
                    new_index_start = len(self.page_items)
                    new_index_end = new_index_start + len(doc)
                    for page_num, real_index in enumerate(range(new_index_start, new_index_end)):
                        # Create PageItem for each page, including image data
                        page_name = f"{filename} - Page {page_num + 1}"
                        self._append_page_item(PageItem(page_name, real_index, self.main_document, True))                    


    # Function to update the preview image when a page is selected from the listbox
    def _show_preview(self, event):
        selected_page = self.page_listbox.curselection()
        if selected_page:
            selected_page = selected_page[0]                  
            
            # Create a Tkinter-compatible PhotoImage from the in-memory PNG
            img = PhotoImage(data=self.page_items[selected_page].get_page_as_png().getvalue())  # Load image from byte stream
            
            # Update the label with the preview
            self.canvas_image_label.config(image=img)
            self.canvas_image_label.image = img  # Keep a reference to avoid garbage collection
            
            # Update the current page label
            self.current_page_label.config(text=f"Current Page: {self.page_items[selected_page].page_name}")


    # Function to toggle the selected state of a page and update the display
    def _toggle_selection(self):
        selected_page = self.page_listbox.curselection()
        if selected_page:
            selected_page = selected_page[0]
            # Toggle the 'selected' status of the page in the internal state
            page_item = self.page_items[selected_page]
            page_item.selected = not page_item.selected
            
            # Update colors based on internal selection state
            self._update_colors(selected_page)


    # Function to update font color based on selection state
    def _update_colors(self, index):
        font_color = 'green' if self.page_items[index].selected else 'black'
        self.page_listbox.itemconfigure(index, {'fg': font_color, 'selectforeground': font_color})


    def __init__(self):
        self.page_items:list[PageItem] = []
        self.main_document:fitz.Document|None = None
                
        # Create the main window
        self.root_window:tk.Tk = tk.Tk()
        self.root_window.title("Organize PDF file")
        menubar = tk.Menu(self.root_window)
        self.root_window.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)

        file_menu.add_command(label="Load", command=self._menu_load)
        file_menu.add_command(label="Save As", command=self._menu_save_as)        

        # Main frame
        main_frame = tk.Frame(self.root_window)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Left side frame for Listbox and Scrollbar
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.page_listbox = tk.Listbox(left_frame, height=15, width=25, selectmode=tk.SINGLE)
        self.page_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(left_frame, orient="vertical", command=self.page_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.page_listbox.config(yscrollcommand=scrollbar.set)

        # Right side frame for image preview and current page label
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=5)

        # Canvas/Label to display page preview
        canvas_frame = tk.Frame(right_frame)  # Frame for image preview to control height
        canvas_frame.pack(fill="both", expand=True)

        self.canvas_image_label = tk.Label(canvas_frame)
        self.canvas_image_label.pack(fill="both", expand=True)  # Image will take up full height of the available space

        # Current page label
        self.current_page_label = tk.Label(right_frame, text="Current Page: 1", font=("Arial", 10))
        self.current_page_label.pack(fill="x", pady=5)  # Label takes full width but fixed height

        # Button for toggling page selection
        select_button = tk.Button(self.root_window, text="Toggle Selection", command=self._toggle_selection)
        select_button.pack(pady=5)

        # Bind the Listbox selection to update the preview
        self.page_listbox.bind("<<ListboxSelect>>", self._show_preview)
        self.page_listbox.bind("<Button-1>", self._start_listbox_item_drag)
        self.page_listbox.bind("<B1-Motion>", self._during_listbox_item_drag)
        self.page_listbox.bind("<ButtonRelease-1>", self._stop_listbox_item_drag)        

    def _start_listbox_item_drag(self, event):
        self.drag_start_index = self.page_listbox.nearest(event.y)
        self.drag_preview_index = None

    def _during_listbox_item_drag(self, event):
        if not hasattr(self, "drag_start_index"):
            return
        
        target_index = self.page_listbox.nearest(event.y)

        if target_index != self.drag_preview_index:
            # Clear previous highlight
            if self.drag_preview_index is not None:
                self.page_listbox.itemconfigure(self.drag_preview_index, background='white')

            # Apply new highlight
            self.page_listbox.itemconfigure(target_index, background='blue')

            self.drag_preview_index = target_index

    def _stop_listbox_item_drag(self, event):
        if not hasattr(self, "drag_start_index"):
            return
        
        if self.drag_preview_index is not None:
            # Remove highlight
            self.page_listbox.itemconfigure(self.drag_preview_index, background="white")

            # Final move
            from_index = self.drag_start_index
            to_index = self.drag_preview_index

            if to_index != from_index:
                # --- move in Listbox ---
                text = self.page_listbox.get(from_index)
                self.page_listbox.delete(from_index)
                self.page_listbox.insert(to_index, text)

                # --- move in data list ---
                self.page_items.insert(to_index, self.page_items.pop(from_index))

                # Update color to match internal state
                self._update_colors(to_index)
                self._update_colors(from_index)

        # Cleanup
        del self.drag_start_index
        self.drag_preview_index = None

    def _menu_load(self):
        # Allow selecting multiple PDFs
        filepaths = SystemFileDialog.askopenfilenames(
            title="Open PDF files",
            filetypes=[("PDF Files", "*.pdf")],
        )
        if not filepaths:
            return
        self.add_pdf(filepaths)

    def _menu_save_as(self):
        filepath = SystemFileDialog.asksaveasfilename(
            defaultextension=".pdf",
            title="Save PDF As",
            filetypes=[("PDF Files", "*.pdf")],
        )
        if not filepath:
            return

        self.save_arranged_pages_as(filepath)
    
    def save_arranged_pages_as(self, file_path:str)->None:
        selected_pages = []
        for page_item in self.page_items:
            if page_item.selected:
                selected_pages.append(page_item.page_index)
        
        with fitz.open("pdf", self.main_document.write()) as working_copy:
            working_copy.select(selected_pages)
            working_copy.save(filename=file_path)

    def mainloop(self)->None:
        # Start the Tkinter event loop
        self.root_window.mainloop()

# Main function to parse command-line argument and run the app
def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Display PDF page previews using Tkinter.")
    parser.add_argument("pdf_path", help="Path to the PDF file.", action='store', nargs='*' )
    args = parser.parse_args()
    
    # Run the application with the provided PDF path
    pdf_dialog = OrganizePdfDialog()
    if args.pdf_path is not None and len(args.pdf_path)>0:
        pdf_dialog.add_pdf(args.pdf_path)

    pdf_dialog.mainloop()


# Entry point of the script
if __name__ == "__main__":
    main()