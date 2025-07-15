import json
import os
import re
from lxml import etree
from zipfile import ZipFile
from .skip_pipeline import should_translate
from config.log_config import app_logger

def extract_word_content_to_json(file_path):
    # Extract Word document content and save as JSON for translation
    with ZipFile(file_path, 'r') as docx:
        document_xml = docx.read('word/document.xml')
        
        # Get all header and footer files
        header_footer_files = [name for name in docx.namelist() 
                              if name.startswith('word/header') or name.startswith('word/footer')]
        
        # Read all header and footer content
        header_footer_content = {}
        for hf_file in header_footer_files:
            header_footer_content[hf_file] = docx.read(hf_file)

    namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    document_tree = etree.fromstring(document_xml)

    content_data = []
    item_id = 0
    
    # Get all paragraphs and tables for processing
    block_elements = document_tree.xpath('.//*[self::w:p or self::w:tbl]', namespaces=namespaces)
    
    # Process all paragraphs and tables in main document
    for element in block_elements:
        element_type = element.tag.split('}')[-1]
        element_index = block_elements.index(element)
        
        if element_type == 'p':
            # Check paragraph properties
            is_heading = bool(element.xpath('.//w:pStyle[@w:val="Heading1" or @w:val="Heading2" or @w:val="Heading3"]', namespaces=namespaces))
            has_numbering = bool(element.xpath('.//w:numPr', namespaces=namespaces))
            
            # Check if this is a table of contents entry
            is_toc_entry = bool(element.xpath('.//w:fldChar[@w:fldCharType="begin"]/../following-sibling::w:r[w:instrText[contains(text(), "TOC")]]', namespaces=namespaces)) or \
                          bool(element.xpath('.//w:hyperlink', namespaces=namespaces))
            
            if is_toc_entry:
                # Process TOC entries as individual text nodes (no concatenation)
                runs = element.xpath('.//w:r', namespaces=namespaces)
                for run_idx, run in enumerate(runs):
                    # Skip page number fields
                    if run.xpath('.//w:fldChar', namespaces=namespaces):
                        continue
                        
                    text_nodes = run.xpath('.//w:t', namespaces=namespaces)
                    for text_idx, text_node in enumerate(text_nodes):
                        text_content = text_node.text if text_node.text else ""
                        
                        if text_content.strip() and should_translate(text_content):
                            item_id += 1
                            content_data.append({
                                "id": item_id,
                                "count_src": item_id,
                                "type": "toc_text_node",
                                "element_index": element_index,
                                "run_index": run_idx,
                                "text_index": text_idx,
                                "value": text_content.replace("\n", "␊").replace("\r", "␍")
                            })
            else:
                # Process regular paragraphs with text concatenation
                full_text = ""
                runs = element.xpath('.//w:r', namespaces=namespaces)
                for run in runs:
                    text_nodes = run.xpath('.//w:t', namespaces=namespaces)
                    for text_node in text_nodes:
                        full_text += text_node.text if text_node.text else ""
                
                numbering_style = None
                if has_numbering:
                    numbering_props = element.xpath('.//w:numPr', namespaces=namespaces)
                    if numbering_props:
                        numbering_style = etree.tostring(numbering_props[0], encoding='unicode')
                
                if full_text and should_translate(full_text):
                    item_id += 1
                    content_data.append({
                        "id": item_id,
                        "count_src": item_id,
                        "type": "paragraph",
                        "is_heading": is_heading,
                        "has_numbering": has_numbering,
                        "numbering_style": numbering_style,
                        "element_index": element_index,
                        "value": full_text.replace("\n", "␊").replace("\r", "␍")
                    })
        
        # Process table cells
        elif element_type == 'tbl':
            table_cells = []
            rows = element.xpath('.//w:tr', namespaces=namespaces)
            
            for row_idx, row in enumerate(rows):
                cells = row.xpath('.//w:tc', namespaces=namespaces)
                
                for cell_idx, cell in enumerate(cells):
                    cell_text = ""
                    
                    cell_paragraphs = cell.xpath('.//w:p', namespaces=namespaces)
                    for cell_para_idx, cell_paragraph in enumerate(cell_paragraphs):
                        para_text = ""
                        cell_runs = cell_paragraph.xpath('.//w:r', namespaces=namespaces)
                        
                        for cell_run in cell_runs:
                            cell_text_nodes = cell_run.xpath('.//w:t', namespaces=namespaces)
                            for cell_text_node in cell_text_nodes:
                                para_text += cell_text_node.text if cell_text_node.text else ""
                        
                        if para_text:
                            cell_text += para_text
                            if cell_para_idx < len(cell_paragraphs) - 1:
                                cell_text += "\n"
                    
                    cell_text = cell_text.strip()
                    if cell_text and should_translate(cell_text):
                        item_id += 1
                        table_cells.append({
                            "id": item_id,
                            "count_src": item_id,
                            "type": "table_cell",
                            "table_index": element_index,
                            "row": row_idx,
                            "col": cell_idx,
                            "value": cell_text.replace("\n", "␊").replace("\r", "␍")
                        })
            
            content_data.extend(table_cells)
    
    # Process headers and footers
    for hf_file, hf_xml in header_footer_content.items():
        hf_tree = etree.fromstring(hf_xml)
        hf_type = "header" if "header" in hf_file else "footer"
        hf_number = os.path.basename(hf_file).split('.')[0]  # Extract header1, footer2, etc.
        
        # Process paragraphs in header/footer
        hf_paragraphs = hf_tree.xpath('.//w:p', namespaces=namespaces)
        for p_idx, paragraph in enumerate(hf_paragraphs):
            paragraph_text = ""
            runs = paragraph.xpath('.//w:r', namespaces=namespaces)
            
            for run in runs:
                text_nodes = run.xpath('.//w:t', namespaces=namespaces)
                for text_node in text_nodes:
                    paragraph_text += text_node.text if text_node.text else ""
            
            if paragraph_text and should_translate(paragraph_text):
                item_id += 1
                content_data.append({
                    "id": item_id,
                    "count_src": item_id,
                    "type": "header_footer",
                    "hf_type": hf_type,
                    "hf_file": hf_file,
                    "hf_number": hf_number,
                    "paragraph_index": p_idx,
                    "value": paragraph_text.replace("\n", "␊").replace("\r", "␍")
                })
        
        # Process tables in header/footer
        hf_tables = hf_tree.xpath('.//w:tbl', namespaces=namespaces)
        for tbl_idx, table in enumerate(hf_tables):
            rows = table.xpath('.//w:tr', namespaces=namespaces)
            
            for row_idx, row in enumerate(rows):
                cells = row.xpath('.//w:tc', namespaces=namespaces)
                
                for cell_idx, cell in enumerate(cells):
                    cell_text = ""
                    
                    cell_paragraphs = cell.xpath('.//w:p', namespaces=namespaces)
                    for cell_para_idx, cell_paragraph in enumerate(cell_paragraphs):
                        para_text = ""
                        cell_runs = cell_paragraph.xpath('.//w:r', namespaces=namespaces)
                        
                        for cell_run in cell_runs:
                            cell_text_nodes = cell_run.xpath('.//w:t', namespaces=namespaces)
                            for cell_text_node in cell_text_nodes:
                                para_text += cell_text_node.text if cell_text_node.text else ""
                        
                        if para_text:
                            cell_text += para_text
                            if cell_para_idx < len(cell_paragraphs) - 1:
                                cell_text += "\n"
                    
                    cell_text = cell_text.strip()
                    if cell_text and should_translate(cell_text):
                        item_id += 1
                        content_data.append({
                            "id": item_id,
                            "count_src": item_id,
                            "type": "header_footer_table_cell",
                            "hf_type": hf_type,
                            "hf_file": hf_file,
                            "hf_number": hf_number,
                            "table_index": tbl_idx,
                            "row": row_idx,
                            "col": cell_idx,
                            "value": cell_text.replace("\n", "␊").replace("\r", "␍")
                        })

    filename = os.path.splitext(os.path.basename(file_path))[0]
    temp_folder = os.path.join("temp", filename)
    os.makedirs(temp_folder, exist_ok=True)
    json_path = os.path.join(temp_folder, "src.json")
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(content_data, json_file, ensure_ascii=False, indent=4)

    app_logger.info(f"Extracted {len(content_data)} content items from document: {filename}")
    return json_path


def write_translated_content_to_word(file_path, original_json_path, translated_json_path):
    # Write both original and translated content to create a bilingual Word document
    with open(original_json_path, "r", encoding="utf-8") as original_file:
        original_data = json.load(original_file)
    
    with open(translated_json_path, "r", encoding="utf-8") as translated_file:
        translated_data = json.load(translated_file)

    # Create mapping of original and translated content
    content_map = {}
    for item in original_data:
        item_id = str(item.get("id", item.get("count_src")))
        if item_id:
            content_map[item_id] = {
                "original": item.get("value", "").replace("␊", "\n").replace("␍", "\r"),
                "type": item.get("type"),
                "element_index": item.get("element_index"),
                "run_index": item.get("run_index"),
                "text_index": item.get("text_index"),
                "table_index": item.get("table_index"),
                "row": item.get("row"),
                "col": item.get("col"),
                "has_numbering": item.get("has_numbering", False),
                "hf_file": item.get("hf_file"),
                "paragraph_index": item.get("paragraph_index"),
                "hf_type": item.get("hf_type"),
                "hf_number": item.get("hf_number")
            }
    
    # Add translations to the content map
    for item in translated_data:
        item_id = str(item.get("id", item.get("count_src")))
        if item_id and item_id in content_map and "translated" in item:
            content_map[item_id]["translated"] = item["translated"].replace("␊", "\n").replace("␍", "\r")
    
    # Load Word document structure
    with ZipFile(file_path, 'r') as docx:
        document_xml = docx.read('word/document.xml')
        
        # Get header and footer files
        header_footer_files = {}
        for name in docx.namelist():
            if name.startswith('word/header') or name.startswith('word/footer'):
                header_footer_files[name] = docx.read(name)

    namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    document_tree = etree.fromstring(document_xml)
    
    # Parse header/footer XML trees
    header_footer_trees = {}
    for hf_file, hf_content in header_footer_files.items():
        header_footer_trees[hf_file] = etree.fromstring(hf_content)
    
    block_elements = document_tree.xpath('.//*[self::w:p or self::w:tbl]', namespaces=namespaces)

    # Update content with translations
    for item_id, item_data in content_map.items():
        if "translated" not in item_data:
            app_logger.warning(f"No translation found for item ID {item_id}")
            continue
            
        original_text = item_data["original"]
        translated_text = item_data["translated"]
        
        if item_data["type"] == "toc_text_node":
            # Update individual TOC text nodes with bilingual content
            try:
                element_index = item_data.get("element_index")
                run_index = item_data.get("run_index")
                text_index = item_data.get("text_index")
                
                if element_index is None or element_index >= len(block_elements):
                    app_logger.error(f"Invalid element index: {element_index}")
                    continue
                    
                paragraph = block_elements[element_index]
                
                if paragraph.tag.split('}')[-1] != 'p':
                    app_logger.error(f"Element at index {element_index} is not a paragraph")
                    continue
                
                # Find specific text node in TOC
                runs = paragraph.xpath('.//w:r', namespaces=namespaces)
                if run_index >= len(runs):
                    app_logger.error(f"Run index {run_index} out of bounds")
                    continue
                
                run = runs[run_index]
                text_nodes = run.xpath('.//w:t', namespaces=namespaces)
                
                if text_index >= len(text_nodes):
                    app_logger.error(f"Text index {text_index} out of bounds")
                    continue
                
                # Update specific text node with bilingual content (original + translation)
                bilingual_text = f"{original_text} / {translated_text}"
                text_nodes[text_index].text = bilingual_text
                
            except (IndexError, TypeError) as e:
                app_logger.error(f"Error updating TOC text node: {e}")
        
        elif item_data["type"] == "paragraph":
            # Combine original and translated text for regular paragraphs
            bilingual_text = f"{original_text}\n{translated_text}"
            
            try:
                element_index = item_data.get("element_index")
                if element_index is None or element_index >= len(block_elements):
                    app_logger.error(f"Invalid element index: {element_index}")
                    continue
                    
                paragraph = block_elements[element_index]
                
                if paragraph.tag.split('}')[-1] != 'p':
                    app_logger.error(f"Element at index {element_index} is not a paragraph")
                    continue
                
                update_paragraph_text_with_formatting(paragraph, bilingual_text, namespaces, item_data.get("has_numbering", False))
                    
            except (IndexError, TypeError) as e:
                app_logger.error(f"Error finding paragraph with index {item_data.get('element_index')}: {e}")
                
        elif item_data["type"] == "table_cell":
            # Combine original and translated text for table cells
            bilingual_text = f"{original_text}\n{translated_text}"
            
            try:
                table_index = item_data.get("table_index")
                if table_index is None or table_index >= len(block_elements):
                    app_logger.error(f"Invalid table index: {table_index}")
                    continue
                
                table = block_elements[table_index]
                
                if table.tag.split('}')[-1] != 'tbl':
                    app_logger.error(f"Element at index {table_index} is not a table")
                    continue
                
                row_idx = item_data.get("row")
                col_idx = item_data.get("col")
                
                rows = table.xpath('.//w:tr', namespaces=namespaces)
                if row_idx >= len(rows):
                    app_logger.error(f"Row index {row_idx} out of bounds")
                    continue
                    
                row = rows[row_idx]
                cells = row.xpath('.//w:tc', namespaces=namespaces)
                
                if col_idx >= len(cells):
                    app_logger.error(f"Column index {col_idx} out of bounds")
                    continue
                    
                cell = cells[col_idx]
                update_table_cell_text(cell, bilingual_text, namespaces)
                    
            except (IndexError, TypeError) as e:
                app_logger.error(f"Error finding table cell: {e}")
        
        # Handle header and footer content
        elif item_data["type"] == "header_footer":
            bilingual_text = f"{original_text}\n{translated_text}"
            
            try:
                hf_file = item_data.get("hf_file")
                if hf_file not in header_footer_trees:
                    app_logger.error(f"Header/footer file not found: {hf_file}")
                    continue
                
                hf_tree = header_footer_trees[hf_file]
                p_idx = item_data.get("paragraph_index")
                
                paragraphs = hf_tree.xpath('.//w:p', namespaces=namespaces)
                if p_idx >= len(paragraphs):
                    app_logger.error(f"Paragraph index {p_idx} out of bounds in {hf_file}")
                    continue
                
                paragraph = paragraphs[p_idx]
                update_paragraph_text_with_formatting(paragraph, bilingual_text, namespaces, False)
                
            except (IndexError, TypeError) as e:
                app_logger.error(f"Error updating header/footer paragraph: {e}")
        
        elif item_data["type"] == "header_footer_table_cell":
            bilingual_text = f"{original_text}\n{translated_text}"
            
            try:
                hf_file = item_data.get("hf_file")
                if hf_file not in header_footer_trees:
                    app_logger.error(f"Header/footer file not found: {hf_file}")
                    continue
                
                hf_tree = header_footer_trees[hf_file]
                tbl_idx = item_data.get("table_index")
                row_idx = item_data.get("row")
                col_idx = item_data.get("col")
                
                tables = hf_tree.xpath('.//w:tbl', namespaces=namespaces)
                if tbl_idx >= len(tables):
                    app_logger.error(f"Table index {tbl_idx} out of bounds in {hf_file}")
                    continue
                
                table = tables[tbl_idx]
                rows = table.xpath('.//w:tr', namespaces=namespaces)
                
                if row_idx >= len(rows):
                    app_logger.error(f"Row index {row_idx} out of bounds in table in {hf_file}")
                    continue
                
                row = rows[row_idx]
                cells = row.xpath('.//w:tc', namespaces=namespaces)
                
                if col_idx >= len(cells):
                    app_logger.error(f"Column index {col_idx} out of bounds in table in {hf_file}")
                    continue
                
                cell = cells[col_idx]
                update_table_cell_text(cell, bilingual_text, namespaces)
                
            except (IndexError, TypeError) as e:
                app_logger.error(f"Error updating header/footer table cell: {e}")

    # Save modified document files
    temp_folder = "temp"
    os.makedirs(temp_folder, exist_ok=True)
    temp_word_folder = os.path.join(temp_folder, "word")
    os.makedirs(temp_word_folder, exist_ok=True)
    
    # Write modified main document
    modified_doc_path = os.path.join(temp_word_folder, "document.xml")
    with open(modified_doc_path, "wb") as modified_doc:
        modified_doc.write(etree.tostring(document_tree, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    
    # Write modified header and footer files
    header_footer_paths = {}
    for hf_file, hf_tree in header_footer_trees.items():
        file_name = os.path.basename(hf_file)
        modified_hf_path = os.path.join(temp_word_folder, file_name)
        with open(modified_hf_path, "wb") as modified_hf:
            modified_hf.write(etree.tostring(hf_tree, xml_declaration=True, encoding="UTF-8", standalone="yes"))
        header_footer_paths[hf_file] = modified_hf_path

    # Create final translated document
    result_folder = "result"
    os.makedirs(result_folder, exist_ok=True)
    result_path = os.path.join(result_folder, f"{os.path.splitext(os.path.basename(file_path))[0]}_translated.docx")

    with ZipFile(file_path, 'r') as original_doc:
        with ZipFile(result_path, 'w') as new_doc:
            # Copy unchanged files
            for item in original_doc.infolist():
                # Skip the files we've modified
                if item.filename == 'word/document.xml' or item.filename in header_footer_paths:
                    continue
                new_doc.writestr(item, original_doc.read(item.filename))
            
            # Add modified files
            new_doc.write(modified_doc_path, 'word/document.xml')
            for hf_file, hf_path in header_footer_paths.items():
                new_doc.write(hf_path, hf_file)

    app_logger.info(f"Translated Word document saved to: {result_path}")
    return result_path

def update_paragraph_text_with_formatting(paragraph, new_text, namespaces, has_numbering=False):
    # Update paragraph text with formatting, supporting bilingual text
    runs = paragraph.xpath('.//w:r', namespaces=namespaces)
    
    if not runs:
        # If no runs exist, create a new one
        new_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
        new_text_node = etree.SubElement(new_run, f"{{{namespaces['w']}}}t")
        new_text_node.text = new_text
        return
    
    # Save original formatting information
    formatting_elements = {}
    for i, run in enumerate(runs):
        # Collect formatting elements from each run
        formats = run.xpath('./w:rPr/*', namespaces=namespaces)
        if formats:
            formatting_elements[i] = formats
    
    # Clear all existing text nodes
    for run in runs:
        for t in run.xpath('.//w:t', namespaces=namespaces):
            t.getparent().remove(t)
    
    # Split text into original and translation
    text_parts = new_text.split('\n', 1)
    original_text = text_parts[0] if text_parts else ""
    translated_text = text_parts[1] if len(text_parts) > 1 else ""
    
    # Handle paragraphs with numbering
    if has_numbering:
        numbering_match = re.match(r'^(\d+[\.\)]|\w+[\.\)]|\•|\-|\*)\s+(.*)$', original_text)
        
        if numbering_match and len(runs) > 1:
            # Process paragraphs with numbering pattern
            numbering_prefix = numbering_match.group(1) + " "
            remaining_text = numbering_match.group(2)
            
            # First run gets the numbering prefix
            new_text_node = etree.SubElement(runs[0], f"{{{namespaces['w']}}}t")
            new_text_node.text = numbering_prefix
            
            # Second run gets the remaining original text
            if len(runs) > 1:
                new_text_node = etree.SubElement(runs[1], f"{{{namespaces['w']}}}t")
                new_text_node.text = remaining_text
                
                # Add the translation with a line break
                if translated_text:
                    br_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
                    br = etree.SubElement(br_run, f"{{{namespaces['w']}}}br")
                    
                    trans_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
                    if 1 in formatting_elements:
                        rPr = etree.SubElement(trans_run, f"{{{namespaces['w']}}}rPr")
                        for format_elem in formatting_elements[1]:
                            cloned_format = etree.fromstring(etree.tostring(format_elem))
                            rPr.append(cloned_format)
                    
                    trans_text = etree.SubElement(trans_run, f"{{{namespaces['w']}}}t")
                    # Add same numbering prefix to translation for alignment
                    trans_text.text = f"{numbering_prefix}{translated_text}"
            else:
                # If only one run, put everything there
                new_text_node.text = new_text
        else:
            # Regular text with original content
            new_text_node = etree.SubElement(runs[0], f"{{{namespaces['w']}}}t")
            new_text_node.text = original_text
            
            # Add translation with line break
            if translated_text:
                br_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
                br = etree.SubElement(br_run, f"{{{namespaces['w']}}}br")
                
                trans_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
                if 0 in formatting_elements:
                    rPr = etree.SubElement(trans_run, f"{{{namespaces['w']}}}rPr")
                    for format_elem in formatting_elements[0]:
                        cloned_format = etree.fromstring(etree.tostring(format_elem))
                        rPr.append(cloned_format)
                
                trans_text = etree.SubElement(trans_run, f"{{{namespaces['w']}}}t")
                trans_text.text = translated_text
    else:
        # For regular paragraphs
        new_text_node = etree.SubElement(runs[0], f"{{{namespaces['w']}}}t")
        new_text_node.text = original_text
        
        # Add translation with line break
        if translated_text:
            br_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
            br = etree.SubElement(br_run, f"{{{namespaces['w']}}}br")
            
            trans_run = etree.SubElement(paragraph, f"{{{namespaces['w']}}}r")
            if 0 in formatting_elements:
                rPr = etree.SubElement(trans_run, f"{{{namespaces['w']}}}rPr")
                for format_elem in formatting_elements[0]:
                    cloned_format = etree.fromstring(etree.tostring(format_elem))
                    rPr.append(cloned_format)
            
            trans_text = etree.SubElement(trans_run, f"{{{namespaces['w']}}}t")
            trans_text.text = translated_text
        
        # Clear other runs
        for i in range(1, len(runs)):
            for t in runs[i].xpath('.//w:t', namespaces=namespaces):
                if t.getparent() is not None:
                    t.getparent().remove(t)


def update_table_cell_text(cell, new_text, namespaces):
    # Update table cell text with bilingual content (original + translation)
    cell_paragraphs = cell.xpath('.//w:p', namespaces=namespaces)
    
    # Split text into original and translation
    text_parts = new_text.split('\n', 1)
    original_text = text_parts[0] if text_parts else ""
    translated_text = text_parts[1] if len(text_parts) > 1 else ""
    
    # Remove all existing paragraphs from the cell
    for p in list(cell_paragraphs):
        parent = p.getparent()
        if parent is not None:
            parent.remove(p)
    
    # Create a new paragraph for the original text
    orig_p = etree.SubElement(cell, f"{{{namespaces['w']}}}p")
    
    if "\n" in original_text:
        # Handle multiline original text
        original_lines = original_text.split("\n")
        
        # First line
        orig_run = etree.SubElement(orig_p, f"{{{namespaces['w']}}}r")
        orig_text_node = etree.SubElement(orig_run, f"{{{namespaces['w']}}}t")
        orig_text_node.text = original_lines[0]
        
        # Additional lines in separate paragraphs
        for line in original_lines[1:]:
            line_p = etree.SubElement(cell, f"{{{namespaces['w']}}}p")
            line_run = etree.SubElement(line_p, f"{{{namespaces['w']}}}r")
            line_text_node = etree.SubElement(line_run, f"{{{namespaces['w']}}}t")
            line_text_node.text = line
    else:
        # Single line original text
        orig_run = etree.SubElement(orig_p, f"{{{namespaces['w']}}}r")
        orig_text_node = etree.SubElement(orig_run, f"{{{namespaces['w']}}}t")
        orig_text_node.text = original_text
    
    # Add translation in a separate paragraph
    if translated_text:
        trans_p = etree.SubElement(cell, f"{{{namespaces['w']}}}p")
        
        if "\n" in translated_text:
            # Handle multiline translation
            translated_lines = translated_text.split("\n")
            
            # First translation line
            trans_run = etree.SubElement(trans_p, f"{{{namespaces['w']}}}r")
            trans_text_node = etree.SubElement(trans_run, f"{{{namespaces['w']}}}t")
            trans_text_node.text = translated_lines[0]
            
            # Additional translation lines in separate paragraphs
            for line in translated_lines[1:]:
                line_p = etree.SubElement(cell, f"{{{namespaces['w']}}}p")
                line_run = etree.SubElement(line_p, f"{{{namespaces['w']}}}r")
                line_text_node = etree.SubElement(line_run, f"{{{namespaces['w']}}}t")
                line_text_node.text = line
        else:
            # Single line translation
            trans_run = etree.SubElement(trans_p, f"{{{namespaces['w']}}}r")
            trans_text_node = etree.SubElement(trans_run, f"{{{namespaces['w']}}}t")
            trans_text_node.text = translated_text


def update_json_structure_after_translation(original_json_path, translated_json_path):
    # Restructure translated JSON to match original format
    with open(original_json_path, "r", encoding="utf-8") as orig_file:
        original_data = json.load(orig_file)
    
    with open(translated_json_path, "r", encoding="utf-8") as trans_file:
        translated_data = json.load(trans_file)
    
    translations_by_id = {}
    for item in translated_data:
        if "translated" in item:
            item_id = str(item.get("id", item.get("count_src")))
            if item_id:
                translations_by_id[item_id] = item["translated"]
    
    restructured_data = []
    for item in original_data:
        item_id = str(item.get("id", item.get("count_src")))
        if item_id in translations_by_id:
            restructured_data.append({
                "id": item.get("id"),
                "count_src": item.get("count_src"),
                "type": item["type"],
                "translated": translations_by_id[item_id]
            })
    
    with open(translated_json_path, "w", encoding="utf-8") as outfile:
        json.dump(restructured_data, outfile, ensure_ascii=False, indent=4)
    
    app_logger.info(f"Updated translation JSON structure to match original: {translated_json_path}")
    return translated_json_path