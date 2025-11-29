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
    def __init__(self):
        pass

    # Function to load PDF and extract page previews
    def load_pdf(self, pdf_path:str)->tuple[list[PageItem], fitz.Document]:
        filename = os.path.basename(pdf_path)
        doc = fitz.open(pdf_path)
        page_items = []
        
        # Extract previews for each page and create PageItem objects
        for page_num in range(len(doc)):
            # Create PageItem for each page, including image data
            page_name = f"{filename} - Page {page_num + 1}"
            page_item = PageItem(page_name, page_num, doc, True)
            page_items.append(page_item)
        
        return page_items, doc


    # Function to update the preview image when a page is selected from the listbox
    def _show_preview(self, event, listbox, page_items, canvas_image_label, current_page_label):
        selected_page = listbox.curselection()
        if selected_page:
            selected_page = selected_page[0]        
            img_data = page_items[selected_page].get_page_as_png()
            
            # Create a Tkinter-compatible PhotoImage from the in-memory PNG
            img = PhotoImage(data=img_data.getvalue())  # Load image from byte stream
            
            # Update the label with the preview
            canvas_image_label.config(image=img)
            canvas_image_label.image = img  # Keep a reference to avoid garbage collection
            
            # Update the current page label
            current_page_label.config(text=f"Current Page: {page_items[selected_page].page_name}")


    # Function to toggle the selected state of a page and update the display
    def _toggle_selection(self, listbox, page_items):
        selected_page = listbox.curselection()
        if selected_page:
            selected_page = selected_page[0]
            # Toggle the 'selected' status of the page in the internal state
            page_items[selected_page].selected = not page_items[selected_page].selected
            
            # Update colors based on internal selection state
            self._update_colors(listbox, page_items, selected_page)


    # Function to update font color based on selection state
    def _update_colors(self, listbox, page_items, index):
        font_color = 'green' if page_items[index].selected else 'black'
        listbox.itemconfigure(index, {'fg': font_color, 'selectforeground': font_color})


    # Create the main Tkinter window
    def create_gui(self, pdf_path):
        page_items, doc = self.load_pdf(pdf_path)
        
        # Create the main window
        root = tk.Tk()
        root.title("PDF Page Previewer")

        # Main frame
        main_frame = tk.Frame(root)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Left side frame for Listbox and Scrollbar
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        listbox = tk.Listbox(left_frame, height=15, width=25, selectmode=tk.SINGLE)
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(left_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)

        for i, page_item in enumerate(page_items):
            listbox.insert(tk.END, page_item.page_name)
            self._update_colors(listbox, page_items, i)

        # Right side frame for image preview and current page label
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=5)

        # Canvas/Label to display page preview
        canvas_frame = tk.Frame(right_frame)  # Frame for image preview to control height
        canvas_frame.pack(fill="both", expand=True)

        canvas_image_label = tk.Label(canvas_frame)
        canvas_image_label.pack(fill="both", expand=True)  # Image will take up full height of the available space

        # Current page label
        current_page_label = tk.Label(right_frame, text="Current Page: 1", font=("Arial", 10))
        current_page_label.pack(fill="x", pady=5)  # Label takes full width but fixed height

        # Button for toggling page selection
        select_button = tk.Button(root, text="Toggle Selection", command=lambda: self._toggle_selection(listbox, page_items))
        select_button.pack(pady=5)

        # Bind the Listbox selection to update the preview
        listbox.bind("<<ListboxSelect>>", lambda event: self._show_preview(event, listbox, page_items, canvas_image_label, current_page_label))        

        # Start the Tkinter event loop
        root.mainloop()


# Main function to parse command-line argument and run the app
def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Display PDF page previews using Tkinter.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    args = parser.parse_args()
    
    # Run the application with the provided PDF path
    OrganizePdfDialog().create_gui(args.pdf_path)


# Entry point of the script
if __name__ == "__main__":
    main()