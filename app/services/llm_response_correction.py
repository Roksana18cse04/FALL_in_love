import json
import re
import html


def extract_json_from_llm(raw):
    """
    LLM থেকে JSON extract করে সব ধরনের edge case handle করে।
    """
    # Already a dict?
    if isinstance(raw, dict):
        return raw
    
    if not isinstance(raw, str):
        raise TypeError("LLM response must be a string or dict.")
    
    raw = raw.strip()
    
    # Step 1: HTML entities decode করুন (যেমন &quot; → ")
    raw = html.unescape(raw)
    
    # Step 2: Markdown fence remove করুন
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    
    # Step 3: JSON parse করার চেষ্টা করুন
    if cleaned.startswith("{") or cleaned.startswith("["):
        try:
            parsed = json.loads(cleaned)
            
            # ✅ Check for nested JSON in answer field
            if isinstance(parsed, dict) and "answer" in parsed:
                answer = parsed["answer"]
                
                # যদি answer field-এ আবার JSON থাকে
                if isinstance(answer, str) and answer.strip().startswith("{"):
                    print("⚠️ NESTED JSON detected in answer field")
                    try:
                        nested = json.loads(answer)
                        if isinstance(nested, dict) and "answer" in nested:
                            parsed["answer"] = nested["answer"]
                            if "used_document" in nested:
                                parsed["used_document"] = nested["used_document"]
                    except:
                        pass  # Keep original if nested parsing fails
            
            return parsed
        
        except json.JSONDecodeError as e:
            print(f"⚠️ Standard JSON parsing failed: {e}")
            
            # 🔧 FALLBACK 1: Control character fix করে আবার try করুন
            try:
                # Replace actual newlines with \n
                fixed = cleaned.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                parsed = json.loads(fixed)
                print("✅ Fixed by escaping control characters")
                return parsed
            except json.JSONDecodeError:
                print("⚠️ Control character fix didn't work")
            
            # 🔧 FALLBACK 2: Regex extraction
            try:
                # Pattern: "answer": "anything", "used_document": true/false
                pattern = r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"used_document"\s*:\s*(true|false)'
                match = re.search(pattern, cleaned, re.DOTALL)
                
                if match:
                    answer_text = match.group(1)
                    # Unescape common escapes
                    answer_text = answer_text.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                    used_doc = match.group(2) == "true"
                    
                    print("✅ Extracted using regex fallback")
                    return {
                        "answer": answer_text,
                        "used_document": used_doc
                    }
            except Exception as regex_error:
                print(f"⚠️ Regex extraction failed: {regex_error}")
            
            # 🔧 FALLBACK 3: ast.literal_eval (Python dict syntax)
            try:
                import ast
                # Replace true/false with True/False for Python
                python_style = cleaned.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                parsed = ast.literal_eval(python_style)
                print("✅ Parsed using ast.literal_eval")
                return parsed
            except Exception as ast_error:
                print(f"⚠️ ast.literal_eval failed: {ast_error}")
            
            # 🔧 FALLBACK 4: Manual extraction যদি সব fail করে
            try:
                # Extract answer content between first "answer": and last "used_document":
                answer_start = cleaned.find('"answer"')
                used_doc_pos = cleaned.rfind('"used_document"')
                
                if answer_start != -1 and used_doc_pos != -1:
                    # Extract answer value
                    answer_part = cleaned[answer_start:used_doc_pos]
                    
                    # Find the actual answer text
                    colon_pos = answer_part.find(':')
                    if colon_pos != -1:
                        answer_value = answer_part[colon_pos+1:].strip()
                        
                        # Remove leading/trailing quotes and comma
                        answer_value = answer_value.strip('",').strip()
                        
                        # Extract used_document value
                        used_doc_part = cleaned[used_doc_pos:]
                        used_doc_value = 'true' in used_doc_part.lower()
                        
                        print("✅ Extracted using manual parsing")
                        return {
                            "answer": answer_value,
                            "used_document": used_doc_value
                        }
            except Exception as manual_error:
                print(f"⚠️ Manual extraction failed: {manual_error}")
            
            # যদি সব fallback fail করে
            raise ValueError(f"All JSON parsing methods failed. Original error: {e}")
    
    # যদি JSON-like না হয়
    print("⚠️ Response doesn't look like JSON, treating as plain text")
    return {"answer": cleaned, "used_document": False}


# 🧪 Test করুন
if __name__ == "__main__":
    # Test case 1: Control character problem (আপনার actual problem)
    test1 = """{
  "answer": "Aged care in Australia is primarily governed by the Aged Care Act 1997. This Act sets the framework for the provision of aged care services in the country. Here's what you need to know about it:
1. **Purpose**: The Act aims to provide older people in Australia with access to quality care services that protect their health and wellbeing.",
  "used_document": false
}"""
    
    print("=" * 60)
    print("Test 1: Control characters (real newlines)")
    print("=" * 60)
    try:
        result = extract_json_from_llm(test1)
        print("✅ SUCCESS!")
        print(f"Answer length: {len(result['answer'])}")
        print(f"Used document: {result['used_document']}")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("Test 2: Escaped version (should work)")
    print("=" * 60)
    test2 = '{"answer": "Aged care in Australia\\n\\n1. **Purpose**: Great", "used_document": false}'
    try:
        result = extract_json_from_llm(test2)
        print("✅ SUCCESS!")
        print(f"Answer: {result['answer'][:50]}...")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("Test 3: With apostrophe")
    print("=" * 60)
    test3 = """{"answer": "Here's what you need to know", "used_document": false}"""
    try:
        result = extract_json_from_llm(test3)
        print("✅ SUCCESS!")
        print(f"Answer: {result['answer']}")
    except Exception as e:
        print(f"❌ FAILED: {e}")