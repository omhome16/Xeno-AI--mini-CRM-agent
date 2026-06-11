import json
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log_path = r'C:\Users\omnaw\.gemini\antigravity-ide\brain\ec62b5aa-4528-4c08-beef-831df5dca153\.system_generated\logs\transcript.jsonl'
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            content = obj.get('content', '')
            if not content:
                continue
                
            # If the log content mentions "mumbai" or "mumbai ones"
            if 'mumbai' in content.lower():
                print(f"=== Step {obj.get('step_index')} ({obj.get('type')}) ===")
                print(content[:600])
                print("-" * 50)

if __name__ == '__main__':
    main()
