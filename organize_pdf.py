import fitz  # PyMuPDF
import tkinter as tk
from tkinter import PhotoImage
import io
import argparse

# Function to load PDF and extract page previews
def load_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    page_previews = []
    
    # Extract previews for each page
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))  # Resize for thumbnail
        
        # Convert Pixmap to an in-memory byte stream (PNG format)
        img_data = io.BytesIO(pix.tobytes("png"))  # Convert to PNG in memory
        page_previews.append(img_data)  # Store the byte stream
    
    return page_previews, doc

# Function to update the preview image when a page is selected from the listbox
def show_preview(event, listbox, page_previews, canvas_image_label, current_page_label):
    selected_page = listbox.curselection()
    if selected_page:
        selected_page = selected_page[0]
        img_data = page_previews[selected_page]
        
        # Create a Tkinter-compatible PhotoImage from the in-memory PNG
        img = PhotoImage(data=img_data.getvalue())  # Load image from byte stream
        
        # Update the label with the preview
        canvas_image_label.config(image=img)
        canvas_image_label.image = img  # Keep a reference to avoid garbage collection
        
        # Update the current page label
        current_page_label.config(text=f"Current Page: {selected_page + 1}")

# Function to update the Listbox with the selected pages (color change)
def update_listbox_with_selection(listbox, selected_pages):
    for i in range(len(listbox.get(0, tk.END))):
        if i in selected_pages:
            listbox.itemconfig(i, {'fg': 'green'})  # Highlight selected page in green
        else:
            listbox.itemconfig(i, {'fg': 'black'})  # Reset text color to black

# Create the main Tkinter window
def create_gui(pdf_path):
    page_previews, doc = load_pdf(pdf_path)
    
    # Track selected pages during the session
    selected_pages = []
    
    # Create the main window
    root = tk.Tk()
    root.title("PDF Page Previewer")

    # Frame for Listbox and Preview Image
    frame = tk.Frame(root)
    frame.pack(padx=10, pady=10)

    # Create the Listbox and add a Scrollbar
    listbox_frame = tk.Frame(frame)
    listbox_frame.pack(side="left", fill="y")

    listbox = tk.Listbox(listbox_frame, height=15, width=20)
    listbox.pack(side="left", fill="y")

    # Add Scrollbar to the Listbox
    scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scrollbar.set)

    # Populate listbox with page numbers
    for i in range(len(page_previews)):
        listbox.insert(tk.END, f"Page {i + 1}")
    
    # Update the listbox with the previously selected pages (highlight selected ones)
    update_listbox_with_selection(listbox, selected_pages)

    # Canvas/Label to show the preview of the selected page
    canvas_image_label = tk.Label(frame)
    canvas_image_label.pack(side="right", padx=10)

    # Label to show the current page number
    current_page_label = tk.Label(frame, text="Current Page: 1")
    current_page_label.pack(side="bottom", padx=10)

    # Function to mark the currently selected page as selected and update the Listbox
    def mark_as_selected():
        selected_page = listbox.curselection()
        if selected_page:
            selected_page = selected_page[0]
            if selected_page not in selected_pages:
                selected_pages.append(selected_page)  # Mark page as selected
                update_listbox_with_selection(listbox, selected_pages)  # Update Listbox colors

    # Button to mark the current page as selected
    mark_button = tk.Button(root, text="Mark as Selected", command=mark_as_selected)
    mark_button.pack(pady=10)

    # Bind the Listbox selection to update the preview
    listbox.bind("<<ListboxSelect>>", lambda event: show_preview(event, listbox, page_previews, canvas_image_label, current_page_label))

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