# This file is licenced under the Apache Licence 2.0
# and was originally taken from https://github.com/davideuler/pdf-translator-for-human/commit/9d793d084e52df5f5ba4f66cd9bb7d4d6ab28f09
from abc import abstractmethod
from collections import Counter
import os
import argparse
import re
import math
import tempfile

import pymupdf
from tqdm import tqdm

class TextTranslator:
    def __init__(self, lang_from:str, lang_to:str):
        self.lang_from=lang_from
        self.lang_to=lang_to
        self.translation_cache=dict()

    def translate_text(self, text:str)->str:
        if text in self.translation_cache:            
            return self.translation_cache[text]
        else:
            result = self._translate_text(text)
            self.translation_cache[text] = result
            return result

    @abstractmethod
    def _translate_text(self, text:str)->str:
        return text

class OpenAiCompatibleTranslator(TextTranslator):
    def __init__(self, lang_from:str, lang_to:str):
        super().__init__(lang_from=lang_from, lang_to=lang_to)
        self.api_key:str|None = os.getenv("OPENAI_API_KEY", 'None')
        self.model:str|None = os.getenv("OPEN_API_MODEL", None)
        self.base_url:str|None = os.getenv("OPEN_API_BASE", None)

        assert self.api_key is not None,  'OPENAI_API_KEY is not set'
        assert self.model is not None,    'OPEN_API_MODEL is not set'
        assert self.base_url is not None, 'OPEN_API_BASE is not set'

        import tiktoken
        self.token_encoder = tiktoken.get_encoding("cl100k_base")        

    def _translate_text(self, text:str)->str:
        #FIXME: this should be configurable since it depends on the model 
        assert len(self.token_encoder.encode(text)) < 3900, 'Textblock is too long' 
        import openai

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        prompt = f"You are an expert in {self.lang_from} and {self.lang_to}.\nPlease provide a high-quality translation of the following text from {self.lang_from} to {self.lang_to}. Only generate the translated text while keeping any existing line breaks.  No additional text or explanation needed.\nText: {text}"


        response = client.chat.completions.create(model=self.model, messages=[{ "role": "user", "content": prompt }])
        
        return response.choices[0].message.content

    def get_token_count(self, text:str)->int:
        return len(self.token_encoder.encode(text))

# Map of supported translators
TRANSLATORS = {
    'openai': OpenAiCompatibleTranslator,
}

def extract_embedded_fonts(doc):
    """
    Extract all embedded fonts from a PyMuPDF document and save to temporary files.

    Args:
        doc (fitz.Document): Opened PyMuPDF document.

    Returns:
        dict: {font_name: temp_file_path}
    """
    fonts_dict = {}
    fonts_found = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        fonts = page.get_fonts(full=True)

        for f in fonts:
            xref = f[0]
            font_name = f[3]  # basefont name
            embedded = f[4]   # True if embedded

            if not embedded or font_name in fonts_found:
                # Skip non-embedded fonts or already extracted fonts
                continue

            fonts_found.append(font_name)
            font_data = doc.extract_font(xref, named=True)

            if not font_data:
                print(f"Warning: Could not extract embedded font: {font_name} and will be ignored")
                fonts_dict[font_name] = None
                continue

            glyphs = font_data.get("glyphs")

            if not glyphs or len(glyphs) == 0:
                print(f"Warning: Embedded font '{font_name}' is likely glyph-less or vector-only and will be ignored")
                fonts_dict[font_name] = None
                continue

            ext = font_data.get("ext", "ttf")
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(font_data["content"])
                tmp_path = tmp.name

            fonts_dict[font_name] = tmp_path
            print(f"INFO: Embedded font '{font_name}' found")
        
    return fonts_dict

def extract_blocks(page, text_flags):
    #blocks = page.get_text("blocks", flags=textflags)
    #text_dicts = page.get_text("dict", flags=textflags)

    text_dict = page.get_text("dict", flags=text_flags)
    blocks = []

    for block in text_dict["blocks"]:
        
        #print(block)
        #print('-------------------------')

        if "lines" not in block:
            continue  # skip non-text blocks

        bbox = block["bbox"]
        block_text = ""
        font_sizes = []
        fonts = []
        rotations = []

        for line in block["lines"]:            
            if 'dir' in line: 
                rotation = line['dir']
                # Fix directions that are not exactly 1 or 0 
                rotation = (round(rotation[0]),round(rotation[1])) 
                if not rotation in rotations:
                    rotations.append(rotation)

            for span in line["spans"]:                
                block_text += span["text"]
                font_sizes.append(span["size"])
                fonts.append(span["font"])
            #block_text += '\r\n'

        if not block_text.strip():
            continue  # skip empty text blocks

        # average font size for this block
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0        
        #avg_font_size = 11
        # most common font in this block
        most_common_font = Counter(fonts).most_common(1)[0][0] if fonts else None

        assert len(rotations) <=1, 'block with multiple rotations are not supported right now'        

        blocks.append({
            "bbox": bbox,
            "text": block_text,
            "avg_font_size": avg_font_size,
            "common_font": most_common_font,
            "rotation": (math.degrees(math.atan2(-1*rotations[0][1], rotations[0][0])) if len(rotations) == 1 else None),
            "dir": rotations[0] if len(rotations) == 1 else None
        })

    return blocks

def sanitize_text(text:str):
    result = text.replace('\r\n', '\n').replace('\r', '\n')
    return (result, not text.replace('\n', '').replace(' ', '').isdigit())

def prepare_pdf_text(text:str, translation:str)->str:
    result = translation
    if translation.endswith('\n') and not text.endswith('\n'):
        result = result.rstrip() #could remove more than is correct
    elif not translation.endswith('\n') and text.endswith('\n'):
        result += '\n'
    return result

def is_valid_translation(text:str, translation:str)->bool:
    # Sometimes, especially with gibberish, a new line get appended
    # no need to clutter the pdf with these results
    return text.strip().lower() != translation.strip().lower()

def insert_text_block(page, fontsize=11, **kwargs):
    while page.insert_textbox(fontsize=fontsize, **kwargs) < 0 and fontsize > 0:
        fontsize -= 1
        if fontsize <= 0: print("Could not render text")


def translate_pdf(input_file: str, source_lang: str, target_lang: str, layer: str = "Text", translator_name: str = "google", text_color: str = "darkred", keep_original: bool = True):
    """
    Translate a PDF file from source language to target language
    
    Args:
        input_file: Path to input PDF file
        source_lang: Source language code (e.g. 'en', 'fr')
        target_lang: Target language code (e.g. 'ko', 'ja') 
        layer: Name of the OCG layer (default: "Text")
        translator_name: Name of the translator to use (default: "google")
        text_color: Color of translated text (default: "darkred")
        keep_original: Whether to keep original text visible (default: True)
    """
    # Define colors
    WHITE = pymupdf.pdfcolor["white"]
    
    # Color mapping
    COLOR_MAP = {
        "darkred": (0.8, 0, 0),
        "black": (0, 0, 0),
        "blue": (0, 0, 0.8),
        "darkgreen": (0, 0.5, 0),
        "purple": (0.5, 0, 0.5),
    }
    
    # Get RGB color values, default to darkred if color not found
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["darkred"])

    # This flag ensures that text will be dehyphenated after extraction.
    textflags = pymupdf.TEXT_DEHYPHENATE

    # Get the translator class
    if translator_name not in TRANSLATORS:
        raise ValueError(f"Unsupported translator: {translator_name}. Available translators: {', '.join(TRANSLATORS.keys())}")
    
    TranslatorClass = TRANSLATORS[translator_name]
    
    # Configure the translator
    translator = TranslatorClass(lang_from=source_lang, lang_to=target_lang)

    # Generate output filename
    output_file = input_file.rsplit('.', 1)[0] + f'-{target_lang}.pdf'

    # Open the document
    doc = pymupdf.open(input_file)
    embedded_fonts = extract_embedded_fonts(doc)

    # Define an Optional Content layer for translation
    ocg_trans = doc.add_ocg(layer, on=True)
    
    # If not keeping original, create a layer for original text and hide it
    if not keep_original:
        ocg_orig = doc.add_ocg("Original", on=False)

    # Iterate over all pages
    for page_index, page in enumerate(tqdm(doc, desc='Translating page...')):        
        # Extract text grouped like lines in a paragraph.
        blocks = extract_blocks(page,textflags)

        # Every block of text is contained in a rectangle ("bbox")
        for block in tqdm(blocks, desc='Translating blocks...', leave=False):
            bbox = block['bbox']  # area containing the text
            text, is_valid_text = sanitize_text(block['text'])  # the text of this block
               
            if is_valid_text:

                # Invoke the actual translation
                translated = prepare_pdf_text(text, translator.translate_text(text))
                
                if is_valid_translation(text, translated):

                    if not keep_original:
                        # Move original text to hidden layer
                        page.insert_htmlbox(
                            bbox,
                            text,
                            css="* {font-family: sans-serif;}",
                            oc=ocg_orig
                        )
                        # Clear original text area in base layer
                        page.draw_rect(bbox, color=None, fill=WHITE)
                    else:
                        # Cover the original text only in translation layer
                        page.draw_rect(bbox, color=None, fill=WHITE, oc=ocg_trans)

                    # Write the translated text in specified color
                    font_name = block['common_font']
                    font_file_path=embedded_fonts.get(font_name,None)
                
                    if font_name not in embedded_fonts or font_file_path is None:
                        #if font_name not in embedded_fonts:
                        #    print(f"WARNING: {font_name} not found")
                        font_name = 'helv'
                    
                    insert_text_block(
                        page,
                        rect=bbox,
                        buffer=translated,
                        fontsize=block['avg_font_size'], 
                        fontname=font_name,
                        fontfile=font_file_path,
                        oc=ocg_trans,
                        color=rgb_color,
                        rotate=block['rotation']
                    )


    #doc.subset_fonts()
    doc.ez_save(output_file)
    print(f"Translated PDF saved as: {output_file}")

def main():
    """
    can be invoked like this:
    ```
    # Basic usage
    python translator_cli.py --source english --target zh-CN input.pdf

    # With custom color and hiding original text
    python translator_cli.py --source english --target zh-CN --color blue --no-original input.pdf

    # Using ChatGPT translator
    export OPENAI_API_KEY=sk-proj-xxxx
    export OPENAI_API_BASE=https://api.xxxx.com/v1
    export OPENAI_API_BASE=http://localhost:8080/v1 #  for local llm api
    export OPENAI_MODEL=default_model
    
    python translator_cli.py --source english --translator chatgpt --target zh-CN input.pdf

    # do not keep original text as an optional layer:
    python translator_cli.py --source english --translator chatgpt --target zh-CN --no-original input.pdf
    
    ```

    The translated content is an optional content layer in the new PDF file. 
    The optional layer can be hidden in Acrobat PDF Reader and Foxit Reader.
    """
    
    parser = argparse.ArgumentParser(description='Translate PDF documents.')
    parser.add_argument('input_file', help='Input PDF file path')
    parser.add_argument('--source', '-s', default='en',
                       help='Source language code (default: en)')
    parser.add_argument('--target', '-t', default='zh-CN',
                       help='Target language code (default: zh-CN)')
    parser.add_argument('--layer', '-l', default='Text',
                       help='Name of the OCG layer (default: Text)')
    parser.add_argument('--translator', '-tr', default='google',
                       choices=list(TRANSLATORS.keys()),
                       help='Translator to use (default: google)')
    parser.add_argument('--color', '-c', default='darkred',
                       choices=['darkred', 'black', 'blue', 'darkgreen', 'purple'],
                       help='Color of translated text (default: darkred)')
    parser.add_argument('--no-original', action='store_true',
                       help='Do not keep original text in base layer (default: False)')

    args = parser.parse_args()

    try:
        translate_pdf(args.input_file, args.source, args.target, args.layer, 
                     args.translator, args.color, not args.no_original)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
