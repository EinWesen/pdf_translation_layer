import fitz  # PyMuPDF
import tkinter as tk
from tkinter import PhotoImage
import io
import argparse
import os


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
    def add_pdf(self, pdf_path:str)->None:
        filename = os.path.basename(pdf_path)
        doc = fitz.open(pdf_path)
        
        # Extract previews for each page and create PageItem objects
        for page_num in range(len(doc)):
            # Create PageItem for each page, including image data
            page_name = f"{filename} - Page {page_num + 1}"
            self._append_page_item(PageItem(page_name, page_num, doc, True))


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
                
        # Create the main window
        self.root_window:tk.Tk = tk.Tk()
        self.root_window.title("PDF Page Previewer")

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

    def mainloop(self)->None:
        # Start the Tkinter event loop
        self.root_window.mainloop()


# Main function to parse command-line argument and run the app
def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Display PDF page previews using Tkinter.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    args = parser.parse_args()
    
    # Run the application with the provided PDF path
    pdf_dialog = OrganizePdfDialog()
    pdf_dialog.add_pdf(args.pdf_path)
    pdf_dialog.mainloop()


# Entry point of the script
if __name__ == "__main__":
    main()