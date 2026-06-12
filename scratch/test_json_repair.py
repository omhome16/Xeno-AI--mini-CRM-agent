import json
import re

def is_closing_quote(s: str, i: int, n: int) -> bool:
    """
    Look ahead from position i + 1 to see if a double quote acts as a closing quote.
    A closing quote in JSON is followed by :, }, ], or , (with optional whitespace).
    """
    j = i + 1
    while j < n and s[j] in (' ', '\t', '\n', '\r'):
        j += 1
    if j >= n:
        return True # EOF is a valid boundary

    char = s[j]
    if char == ':':
        return True
    if char in ('}', ']'):
        return True
    if char == ',':
        # Verify if comma is followed by another key (string + colon) or block end
        j += 1
        while j < n and s[j] in (' ', '\t', '\n', '\r'):
            j += 1
        if j >= n:
            return True
        if s[j] == '}':
            return True
        if s[j] == '"':
            # Find closing quote of the next key, and verify if it's followed by a colon ':'
            k = j + 1
            escaped = False
            while k < n:
                if s[k] == '\\':
                    escaped = not escaped
                elif s[k] == '"' and not escaped:
                    # Found closing quote, check if followed by colon
                    k += 1
                    while k < n and s[k] in (' ', '\t', '\n', '\r'):
                        k += 1
                    if k < n and s[k] == ':':
                        return True
                    break
                else:
                    escaped = False
                k += 1
            return False
        if s[j] == '{':
            return True
        return False
    return False

def repair_json_string(s: str) -> str:
    result = []
    in_string = False
    escape = False
    i = 0
    n = len(s)
    
    while i < n:
        char = s[i]
        
        if char == '\\':
            escape = not escape
            result.append(char)
            i += 1
            continue
            
        if char == '"':
            if escape:
                result.append(char)
                escape = False
                i += 1
                continue
                
            if not in_string:
                in_string = True
                result.append(char)
            else:
                if is_closing_quote(s, i, n):
                    in_string = False
                    result.append(char)
                else:
                    result.append('\\"')
            escape = False
            i += 1
            continue
            
        escape = False
        if char == '\n':
            if in_string:
                result.append('\\n')
            else:
                result.append(char)
        elif char == '\r':
            if in_string:
                result.append('\\r')
            else:
                result.append(char)
        else:
            result.append(char)
        i += 1
        
    return "".join(result)

def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    # Layer 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Layer 2: Try repairing and parsing
    try:
        repaired = repair_json_string(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Layer 3: Extract {...} block
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        extracted = match.group(1)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass
            
        # Layer 4: Try repairing the extracted {...} block
        try:
            repaired_extracted = repair_json_string(extracted)
            return json.loads(repaired_extracted)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Failed to parse JSON response after all repair attempts", text, 0)

# Test cases
bad1 = 'Here is the JSON: {"think_pad": "User clicked "Refine", so let\'s refine.", "action": "brainstorm"}'
bad2 = '{"response": "Line 1\nLine 2"}'
bad3 = '```json\n{"action": "general_chat", "think_pad": "some \\"escaped\\" and "unescaped" quotes"}\n```'
bad4 = '{"think_pad": "User is providing channel and message idea for the existing audience. This is a brainstorm action as the offer details are not fully specified. User wants \"email\", \"sms\" or whatsapp.", "tool_to_call": "create_saved_segment"}'

for idx, bad in enumerate([bad1, bad2, bad3, bad4], 1):
    try:
        res = _parse_json_response(bad)
        print(f"Test {idx} PASSED: {res}")
    except Exception as e:
        print(f"Test {idx} FAILED: {e}")
        # Print repaired string to debug
        try:
            repaired = repair_json_string(bad)
            print(f"  Repaired raw: {repaired}")
        except Exception as re_err:
            print(f"  Repair function failed: {re_err}")



