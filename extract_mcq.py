import pdfplumber
import json
import re
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

def is_yellow(color):
    """Check if color is yellow (1,1,0) or close to it."""
    if not color:
        return False
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        return r > 0.9 and g > 0.9 and b < 0.2
    return False

def get_text_in_rect(chars, rect):
    """Get all text characters that fall within a rectangle."""
    x0, y0, x1, y1 = rect['x0'], rect['top'], rect['x1'], rect['bottom']
    
    text_chars = []
    for char in chars:
        char_cx = (char['x0'] + char['x1']) / 2
        char_cy = (char['top'] + char['bottom']) / 2
        
        if x0 <= char_cx <= x1 and y0 <= char_cy <= y1:
            text_chars.append(char)
    
    text_chars.sort(key=lambda c: (c['top'], c['x0']))
    return ''.join(c['text'] for c in text_chars)

def extract_highlighted_answers(pdf_path):
    """Extract all highlighted (correct) answers from PDF."""
    highlighted = {}  # Will map question_number -> correct_answer_letter
    
    with pdfplumber.open(pdf_path) as pdf:
        current_question_num = None
        
        for page in pdf.pages:
            chars = page.chars
            rects = page.rects if page.rects else []
            text = page.extract_text() or ""
            
            # Find question numbers on this page to associate with highlights
            lines = text.split('\n')
            
            for rect in rects:
                stroke_color = rect.get('stroking_color')
                non_stroking = rect.get('non_stroking_color')
                
                if is_yellow(stroke_color) or is_yellow(non_stroking):
                    rect_text = get_text_in_rect(chars, rect)
                    if rect_text.strip():
                        # Check if it's an option line
                        opt_match = re.match(r'^([A-Da-d])[.)\s]', rect_text.strip())
                        if opt_match:
                            letter = opt_match.group(1).upper()
                            
                            # Find the question number this belongs to
                            # Look at text above this rectangle
                            rect_y = rect['top']
                            
                            # Find the most recent question number before this y position
                            for line in lines:
                                q_match = re.match(r'^(\d+)\.\s+(?!\[)', line.strip())
                                if q_match:
                                    current_question_num = int(q_match.group(1))
                            
                            if current_question_num:
                                highlighted[current_question_num] = letter
    
    return highlighted

def extract_mcqs_from_pdf(pdf_path):
    """Extract MCQ questions from PDF and return as structured data."""
    
    # First, extract all highlighted answers
    print("Extracting highlighted correct answers...")
    correct_answers = {}
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            chars = page.chars
            rects = page.rects if page.rects else []
            text = page.extract_text() or ""
            
            # Track current question number based on page content
            current_q_num = None
            lines = text.split('\n')
            
            # Build a list of (y_position, question_number) for questions on this page
            question_positions = []
            for char_group_y in sorted(set(round(c['top']) for c in chars)):
                line_chars = [c for c in chars if round(c['top']) == char_group_y]
                line_text = ''.join(c['text'] for c in sorted(line_chars, key=lambda x: x['x0']))
                
                # Check if this line starts a question (not metadata)
                q_match = re.match(r'^(\d+)\.\s+[A-Z]', line_text.strip())
                if q_match:
                    q_num = int(q_match.group(1))
                    question_positions.append((char_group_y, q_num))
            
            # Now find highlighted rectangles and match to questions
            for rect in rects:
                stroke_color = rect.get('stroking_color')
                non_stroking = rect.get('non_stroking_color')
                
                if is_yellow(stroke_color) or is_yellow(non_stroking):
                    rect_text = get_text_in_rect(chars, rect)
                    if rect_text.strip():
                        opt_match = re.match(r'^([A-Da-d])[.)\s]', rect_text.strip())
                        if opt_match:
                            letter = opt_match.group(1).upper()
                            rect_y = rect['top']
                            
                            # Find the question this highlight belongs to
                            # It's the most recent question before this y position
                            for q_y, q_num in reversed(question_positions):
                                if q_y < rect_y:
                                    correct_answers[q_num] = letter
                                    break
    
    print(f"Found {len(correct_answers)} correct answers")
    
    # Now extract questions
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    lines = full_text.split('\n')
    questions = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Look for metadata line pattern: "14. [STRONG] (score 0.92)" or "14. [EXACT] (score 1.0)"
        meta_match = re.match(r'^\???(\d+)\.\s*\[(STRONG|EXACT|WEAK)\]\s*\(score\s*[\d.]+\)', line)
        
        if meta_match:
            q_num = int(meta_match.group(1))
            
            # Skip the "(From XXX list: Question XXX)" line
            i += 1
            while i < len(lines) and ('From' in lines[i] and 'list:' in lines[i]):
                i += 1
            
            if i >= len(lines):
                break
            
            # Now we should be at the actual question line
            # It starts with the same question number
            q_line = lines[i].strip()
            
            # Remove leading ?? if present
            q_line = re.sub(r'^\?+', '', q_line).strip()
            
            # Match the question: "14. The fuselage structure..."
            q_match = re.match(r'^(\d+)\.\s+(.+)', q_line)
            
            if q_match:
                q_text = q_match.group(2).strip()
                i += 1
                
                # Continue reading question text until we hit an option
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        i += 1
                        continue
                    # Check if it's an option line
                    if re.match(r'^[A-Da-d][.)\s]', next_line):
                        break
                    # Check if it's a new question metadata
                    if re.match(r'^\???(\d+)\.\s*\[(STRONG|EXACT|WEAK)\]', next_line):
                        break
                    # Check if it's a new question
                    if re.match(r'^\d+\.\s+[A-Z]', next_line):
                        break
                    # It's continuation of the question
                    q_text += " " + next_line
                    i += 1
                
                # Now extract options
                options = {}
                current_opt_letter = None
                current_opt_text = ""
                
                while i < len(lines):
                    next_line = lines[i].strip()
                    
                    if not next_line:
                        i += 1
                        continue
                    
                    # Check if it's a new question metadata (end of current question)
                    if re.match(r'^\???(\d+)\.\s*\[(STRONG|EXACT|WEAK)\]', next_line):
                        break
                    
                    # Check if it's a new question line
                    if re.match(r'^\d+\.\s+[A-Z]', next_line):
                        break
                    
                    # Check if it's an option line
                    opt_match = re.match(r'^([A-Da-d])[.)\s]\s*(.+)', next_line)
                    if opt_match:
                        # Save previous option if exists
                        if current_opt_letter and current_opt_text:
                            options[current_opt_letter] = current_opt_text.strip()
                        
                        current_opt_letter = opt_match.group(1).upper()
                        current_opt_text = opt_match.group(2).strip()
                        i += 1
                        continue
                    
                    # It might be continuation of current option
                    if current_opt_letter:
                        current_opt_text += " " + next_line
                    
                    i += 1
                
                # Save last option
                if current_opt_letter and current_opt_text:
                    options[current_opt_letter] = current_opt_text.strip()
                
                # Clean up question text
                q_text = re.sub(r'\s+', ' ', q_text).strip()
                
                # Create question entry
                q_data = {
                    "question_number": q_num,
                    "question": q_text
                }
                if options:
                    q_data["options"] = options
                
                # Add correct answer if we found it
                if q_num in correct_answers:
                    q_data["correct_answer"] = correct_answers[q_num]
                
                questions.append(q_data)
            else:
                i += 1
        else:
            i += 1
    
    # Sort by question number
    questions.sort(key=lambda x: x['question_number'])
    
    return questions, correct_answers

def main():
    pdf_path = "MCQ .pdf"
    output_path = "mcq_questions.json"
    
    print(f"Extracting questions from: {pdf_path}")
    questions, correct_answers = extract_mcqs_from_pdf(pdf_path)
    
    print(f"Found {len(questions)} questions")
    
    # Count questions with correct answers
    with_answers = sum(1 for q in questions if 'correct_answer' in q)
    print(f"Questions with correct answers: {with_answers}")
    
    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to: {output_path}")
    
    # Print first few questions as preview
    if questions:
        print("\nPreview of first 5 questions:")
        for q in questions[:5]:
            correct = q.get('correct_answer', '?')
            print(f"\nQ{q['question_number']}: {q['question'][:80]}...")
            print(f"  Correct Answer: {correct}")
            if 'options' in q:
                for opt, text in q['options'].items():
                    marker = " ✓" if opt == correct else ""
                    print(f"  {opt}) {text[:50]}{marker}")

if __name__ == "__main__":
    main()
