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
def show_preview(event, listbox, page_previews, canvas_image_label):
    selected_page = listbox.curselection()
    if selected_page:
        selected_page = selected_page[0]
        img_data = page_previews[selected_page]
        
        # Create a Tkinter-compatible PhotoImage from the in-memory PNG
        img = PhotoImage(data=img_data.getvalue())  # Load image from byte stream
        
        # Update the label with the preview
        canvas_image_label.config(image=img)
        canvas_image_label.image = img  # Keep a reference to avoid garbage collection

# Create the main Tkinter window
def create_gui(pdf_path):
    page_previews, doc = load_pdf(pdf_path)
    
    # Create the main window
    root = tk.Tk()
    root.title("PDF Page Previewer")
    
    # Frame for Listbox and Preview Image
    frame = tk.Frame(root)
    frame.pack(padx=10, pady=10)

    # Listbox to show page numbers
    listbox = tk.Listbox(frame, height=15, width=10)
    listbox.pack(side="left", fill="y")

    # Populate listbox with page numbers
    for i in range(len(page_previews)):
        listbox.insert(tk.END, f"Page {i + 1}")

    # Canvas/Label to show the preview of the selected page
    canvas_image_label = tk.Label(frame)
    canvas_image_label.pack(side="right", padx=10)

    # Bind the Listbox selection to update the preview
    listbox.bind("<<ListboxSelect>>", lambda event: show_preview(event, listbox, page_previews, canvas_image_label))

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