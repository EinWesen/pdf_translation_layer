# This file is licenced under the Apache Licence 2.0
# and was originally taken from https://github.com/davideuler/pdf-translator-for-human/commit/9d793d084e52df5f5ba4f66cd9bb7d4d6ab28f09
from abc import abstractmethod
from collections import Counter
import typing
import os
import argparse
import re
import math
import tempfile
import shelve

import pymupdf
from tqdm import tqdm

FALLBACK_FONT_NAME = 'helv'

class TextTranslator:
    def __init__(self, lang_from:str, lang_to:str, translator_cache_file:str=None):
        self.lang_from=lang_from
        self.lang_to=lang_to
        self.translator_cache_file = translator_cache_file
        self.translation_cache=dict()
        if translator_cache_file is not None:
            self.translation_cache=shelve.open(translator_cache_file, writeback=True)

    def sync_cache(self)->None:
        if self.translator_cache_file is not None:
            self.translation_cache.sync()
    
    def close_cache(self)->None:
        if self.translator_cache_file is not None:
            self.translation_cache.close()
        else:
            self.translation_cache=dict()
    
    def translate_text(self, text:str)->str:
        if text in self.translation_cache:            
            return self.translation_cache[text]
        else:
            result = self._execute_prompt(self._create_prompt_text(text))
            if result is not None:
                self.translation_cache[text] = result
                return result
            else:
                return text
    
    def get_request_token_count(self, text:str)->int:
        return len(self._create_prompt_text(text))

    @abstractmethod
    def _get_token_count(self, text:str)->str:
        return len(text)

    @abstractmethod
    def _create_prompt_text(self, text:str)->str:
        return text
    
    @abstractmethod
    def _execute_prompt(self, text:str)->str|None:
        return text

class OpenAiCompatibleTranslator(TextTranslator):
    def __init__(self, lang_from:str, lang_to:str, translator_cache_file:str=None):
        super().__init__(lang_from=lang_from, lang_to=lang_to, translator_cache_file=translator_cache_file)
        self.api_key:str|None = os.getenv("OPENAI_API_KEY", 'None')
        self.model:str|None = os.getenv("OPENAI_API_MODEL", None)
        self.base_url:str|None = os.getenv("OPENAI_API_BASE", None)
        self.model_context_size:int|None = int(os.getenv("LLM_API_MAX_TOKENS", 128000))

        assert self.api_key is not None,  'OPENAI_API_KEY is not set'
        assert self.model is not None,    'OPENAI_API_MODEL is not set'
        assert self.base_url is not None, 'OPENAI_API_BASE is not set'

        import tiktoken
        self.token_encoder = tiktoken.get_encoding("cl100k_base")        

    def _create_prompt(self, text:str)->str:
        return f"You are an expert in {self.lang_from} and {self.lang_to}.\nPlease provide a high-quality translation of the following text from {self.lang_from} to {self.lang_to}. Only generate the translated text while keeping any existing line breaks.  No additional text or explanation needed.Since this text came from OCR it could contain gibberish.In that case just return it unchanged.\nText: {text}"

    def _execute_prompt(self, text:str)->str|None:
        prompt = self._create_prompt(text)

        request_tokens = self._get_token_count(prompt)
        
        # basically we are saying render as much as we think the llm can handle
        # but setting this limit will make sure we can notice if we go over and get cut off
        free_tokens = max(self.model_context_size - request_tokens, self.model_context_size)
        
        import openai

        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        try:
            response = client.chat.completions.create(model=self.model, messages=[{ "role": "user", "content": prompt }], max_completion_tokens=free_tokens)

            if response.choices[0].finish_reason == 'stop':
                return response.choices[0].message.content
            else:
                try:
                    tqdm.write(f"ERROR: LLM did not finish ({response.choices[0].finish_reason}); Usage {response.usage.prompt_tokens} + {response.usage.completion_tokens} of {self.model_context_size} (?)")
                except:
                    pass
                return None            
        except Exception as e:
            try:
                tqdm.write(f"ERROR: LLM did return an exception: {e}")
            except:
                pass
            return None

    def _get_token_count(self, text:str)->int:
        return len(self.token_encoder.encode(text))

class CacheOnlyTranslator(TextTranslator):
    def __init__(self, lang_from:str, lang_to:str, translator_cache_file:str=None):        
        super().__init__(lang_from=lang_from, lang_to=lang_to, translator_cache_file=translator_cache_file)
        if translator_cache_file is None:
            raise ValueError('You need to provide a translator_cache_file to be able to use this translator')
    
    def _execute_prompt(self, text:str)->str|None:
        return None

# Map of supported translators
TRANSLATORS = {
    'openai': OpenAiCompatibleTranslator,
    'cacheonly': CacheOnlyTranslator,
}

def get_usable_fonts(doc, default_font_path:str = None)->typing.Tuple[typing.Dict[str,str], str]:
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
            # TODO: Delete at some point?
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(font_data["content"])
                tmp_path = tmp.name

            fonts_dict[font_name] = tmp_path
            print(f"INFO: Embedded font '{font_name}' found")
    
    default_font_name = FALLBACK_FONT_NAME
    if default_font_path is not None:
        default_font_name = os.path.basename(default_font_path)
        if default_font_name not in fonts_dict or fonts_dict.get(default_font_name) is None:            
            fonts_dict[default_font_name] = default_font_path
            print(f"INFO: Added default font '{default_font_name}'")
        
    return (fonts_dict, default_font_name)

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


def translate_pdf(input_file: str, source_lang: str, target_lang: str, target_layer: str = "Text", translator_name: str = "openai", text_color: str = "blue", keep_original: bool = True, default_font_path:str = None, translator_cache_file:str = None):
    """
    Translate a PDF file from source language to target language
    
    Args:
        input_file: Path to input PDF file
        source_lang: Source language code (e.g. 'en', 'fr')
        target_lang: Target language code (e.g. 'ko', 'ja') 
        target_layer: Name of the OCG layer (default: "Text")
        translator_name: Name of the translator to use (default: "openai")
        text_color: Color of translated text (default: "blue")
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
    rgb_color = COLOR_MAP.get(text_color.lower(), COLOR_MAP["blue"])

    # This flag ensures that text will be dehyphenated after extraction.
    textflags = pymupdf.TEXT_DEHYPHENATE

    # Get the translator class
    if translator_name not in TRANSLATORS:
        raise ValueError(f"Unsupported translator: {translator_name}. Available translators: {', '.join(TRANSLATORS.keys())}")
    
    TranslatorClass = TRANSLATORS[translator_name]
    
    translator = None
    try:
        # Configure the translator
        translator = TranslatorClass(lang_from=source_lang, lang_to=target_lang,translator_cache_file=translator_cache_file)

        # Generate output filename
        output_file = input_file.rsplit('.', 1)[0] + f'-{target_lang}.pdf'

        # Open the document
        doc = pymupdf.open(input_file)
        usable_fonts,default_font_name = get_usable_fonts(doc, default_font_path)

        # Define an Optional Content layer for translation
        ocg_trans = doc.add_ocg(target_layer, on=True)
        
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

                        font_name = block['common_font']
                        
                        if font_name not in usable_fonts and font_name != default_font_name: 
                            font_name = default_font_name
                        
                        font_file_path = usable_fonts.get(font_name,None)
                        if font_file_path is None:
                            font_name = FALLBACK_FONT_NAME
                        
                        # Write the translated text in specified color
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
            
            translator.sync_cache()

        #doc.subset_fonts()
        doc.ez_save(output_file)
        print(f"Translated PDF saved as: {output_file}")

    except:
        if translator is not None:
            translator.close_cache()
        raise

def analyze_pdf(input_file: str, translator_name: str = "openai", token_target=None):
    
    print('Opening PDF ...')
    doc = pymupdf.open(input_file)
    
    print('Checking fonts ...')
    
    fonts, _ = get_usable_fonts(doc, None)
    for f in fonts.values():
        if f is not None: break
    else:
        print('Providing a default font is ecouraged')
    print('-------------------------------------')
    
    print('Analyzing tokens ...')
    TranslatorClass = TRANSLATORS[translator_name]
    translator = TranslatorClass(lang_from=None, lang_to=None,translator_cache_file=None)

    total_request_tokens = 0
    max_request_token_length = 0
    total_requests = 0
    cache_hits = 0
    total_pages = 0
    total_blocks = 0
    total_token_target_hits = 0

    # Iterate over all pages
    for page_index, page in enumerate(tqdm(doc, desc='Iterating pages ...')):        
        # Extract text grouped like lines in a paragraph.
        blocks = extract_blocks(page, pymupdf.TEXT_DEHYPHENATE)

        # Every block of text is contained in a rectangle ("bbox")
        for block in tqdm(blocks, desc='Iterating blocks...', leave=False):
            bbox = block['bbox']  # area containing the text
            text, is_valid_text = sanitize_text(block['text'])  # the text of this block
                
            if is_valid_text:
                if text not in translator.translation_cache:
                    tokens = translator.get_request_token_count(text)
                    if token_target > 0 and tokens>token_target:
                        print(f'INFO: {tokens} > target {token_target}')
                        total_token_target_hits += 1

                    max_request_token_length = max(tokens, max_request_token_length)
                    total_request_tokens += tokens
                    total_requests += 1                    
                    translator.translation_cache[text] = str(tokens) # it is only important, thet the key exists
                else:
                    cache_hits += 1

            total_blocks += 1
        total_pages += 1
    
    print(f"Total pages:", total_pages)
    print(f"Total text blocks:", total_blocks)
    print(f"Total requests needed:", total_requests)
    print(f"Total requests tokens:", total_request_tokens)
    print(f"Total requests exceeding target token limit:", total_token_target_hits)
    print(f"Max request token length:", max_request_token_length)
    print(f"Cache hits:", cache_hits)

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
    main_parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False)
    main_parser.add_argument("-h", "--help", help="show help message and exit", action="store_true")

    subparsers = main_parser.add_subparsers(title='subcommands', description='(use -h for more info about each command)', help=' ... One of ...', dest="sub_command")
    parser = subparsers.add_parser("translate", help="Translate a PDF document.", add_help=True)

    parser.add_argument('--translator', '-tr', default='openai',
                       choices=list(TRANSLATORS.keys()),
                       help='Translator to use')
    
    parser.add_argument('input_file', help='Input PDF file path')
    parser.add_argument('--source', '-s', default='en',
                       help='Source language code (default: en)')
    parser.add_argument('--target', '-t', default='zh-CN',
                       help='Target language code (default: zh-CN)')
    parser.add_argument('--layer', '-l', default='Text',
                       help='Name of the OCG layer (default: Text)')
    parser.add_argument('--color', '-c', default='darkred',
                       choices=['darkred', 'black', 'blue', 'darkgreen', 'purple'],
                       help='Color of translated text (default: darkred)')
    parser.add_argument('--no-original', action='store_true',
                       help='Do not keep original text in base layer (default: False)')
    parser.add_argument('--default-font-path', default=None,
                       help=f'Font to use if no embedded font can be found (default: Internal font {FALLBACK_FONT_NAME})')
    parser.add_argument('--translator-cache-file', default=None,
                       help=f'Path to persistent response cache (default: None')

    parser2 = subparsers.add_parser("info", help="Show analytic information about the PDF", add_help=True)
    parser2.add_argument('--translator', '-tr', default='openai',
                       choices=list(TRANSLATORS.keys()),
                       help='Translator to use')    
    parser2.add_argument('input_file', help='Input PDF file path')

    args = main_parser.parse_args()

    try:
        if args.sub_command is None:
            if args.help:
                main_parser.print_usage()
                print('-------------------------------------------------')
                parser.print_help()
                print('-------------------------------------------------')
                parser2.print_help()
            else:
                parser.print_usage()
                parser2.print_usage()

        elif args.sub_command == 'translate':
            translate_pdf(args.input_file, args.source, args.target, args.layer, args.translator, args.color, not args.no_original, args.default_font_path, args.translator_cache_file)
        elif args.sub_command == 'info':
            analyze_pdf(args.input_file, args.translator, 650)
        else:
            pass

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
