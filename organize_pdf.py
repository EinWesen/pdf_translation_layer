import fitz  # PyMuPDF
import tkinter as tk
from tkinter import PhotoImage
import io
import argparse


# Define a class to store information about each page
class PageItem:
    def __init__(self, page_name, page_index, img_data, selected=False):
        self.page_name = page_name  # e.g., "Page 1"
        self.page_index = page_index  # Actual page index in the PDF
        self.img_data = img_data  # Image data (PNG byte stream) for the page preview
        self.selected = selected  # Whether the page is selected (internal state)


# Function to load PDF and extract page previews
def load_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    page_items = []
    
    # Extract previews for each page and create PageItem objects
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))  # Resize for thumbnail
        
        # Convert Pixmap to an in-memory byte stream (PNG format)
        img_data = io.BytesIO(pix.tobytes("png"))  # Convert to PNG in memory
        
        # Create PageItem for each page, including image data
        page_name = f"Page {page_num + 1}"
        page_item = PageItem(page_name, page_num, img_data)
        page_item.selected = True
        page_items.append(page_item)
    
    return page_items, doc

# Function to update the preview image when a page is selected from the listbox
def show_preview(event, listbox, page_items, canvas_image_label, current_page_label):
    selected_page = listbox.curselection()
    if selected_page:
        selected_page = selected_page[0]        
        img_data = page_items[selected_page].img_data
        
        # Create a Tkinter-compatible PhotoImage from the in-memory PNG
        img = PhotoImage(data=img_data.getvalue())  # Load image from byte stream
        
        # Update the label with the preview
        canvas_image_label.config(image=img)
        canvas_image_label.image = img  # Keep a reference to avoid garbage collection
        
        # Update the current page label
        current_page_label.config(text=f"Current Page: {page_items[selected_page].page_name}")


# Function to toggle the selected state of a page and update the display
def toggle_selection(listbox, page_items):
    selected_page = listbox.curselection()
    if selected_page:
        selected_page = selected_page[0]
        # Toggle the 'selected' status of the page in the internal state
        page_items[selected_page].selected = not page_items[selected_page].selected
        
        # Update colors based on internal selection state
        update_colors(listbox, page_items, selected_page)


# Function to update font color based on selection state
def update_colors(listbox, page_items, index):
    # Determine the font color based on the internal 'selected' state
    font_color = 'green' if page_items[index].selected else 'black'
    
    # Set the foreground (font) color
    listbox.itemconfigure(index, {'fg': font_color, 'selectforeground': font_color})
    #listbox.itemconfig(index, {'fg': font_color})

# Create the main Tkinter window
def create_gui(pdf_path):
    page_items, doc = load_pdf(pdf_path)
    
    # Create the main window
    root = tk.Tk()
    root.title("PDF Page Previewer")

    # Frame for Listbox and Preview Image
    frame = tk.Frame(root)
    frame.pack(padx=10, pady=10)

    # Create the Listbox and add a Scrollbar
    listbox_frame = tk.Frame(frame)
    listbox_frame.pack(side="left", fill="y")

    listbox = tk.Listbox(listbox_frame, height=15, width=20, selectmode=tk.SINGLE)
    listbox.pack(side="left", fill="y")

    # Add Scrollbar to the Listbox
    scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scrollbar.set)

    # Populate listbox with page names
    for i, page_item in enumerate(page_items):
        listbox.insert(tk.END, page_item.page_name)
        update_colors(listbox, page_items, i)
    
    # Canvas/Label to show the preview of the selected page
    canvas_image_label = tk.Label(frame)
    canvas_image_label.pack(side="right", padx=10)

    # Label to show the current page number
    current_page_label = tk.Label(frame, text="Current Page: 1")
    current_page_label.pack(side="bottom", padx=10)

    # Button to mark a page as selected
    select_button = tk.Button(root, text="Toggle Selection", command=lambda: toggle_selection(listbox, page_items))
    select_button.pack(pady=10)

    # Bind the Listbox selection to update the preview
    listbox.bind("<<ListboxSelect>>", lambda event: show_preview(event, listbox, page_items, canvas_image_label, current_page_label))        

    # Start the Tkinter event loop
    root.mainloop()

# Main function to parse command-line argument and run the app
def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Display PDF page previews using Tkinter.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    args = parser.parse_args()
    
    # Run the application with the provided PDF path
    create_gui(args.pdf_path)


# Entry point of the script
if __name__ == "__main__":
    main()