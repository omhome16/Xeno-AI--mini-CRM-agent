import asyncio
import json
import urllib.request
import urllib.parse
import sys

async def main():
    # 1. Start Chat Request
    url = "http://localhost:8000/api/chat"
    payload = {
        "message": "i want to run a campaign for customers in banglore",
        "mode": "brainstorm"
    }
    data = json.dumps(payload).encode("utf-8")
    
    print("Sending POST request to /api/chat...")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            print(f"Response: {res_json}")
            conversation_id = res_json.get("conversation_id")
    except Exception as e:
        print(f"Error calling /api/chat: {e}")
        return

    # 2. Listen to SSE Stream
    sse_url = f"http://localhost:8000/api/chat/stream/{conversation_id}"
    print(f"Listening to SSE stream: {sse_url}")
    
    def read_sse():
        current_event_type = None
        try:
            req_sse = urllib.request.Request(sse_url)
            with urllib.request.urlopen(req_sse) as sse_res:
                for line in sse_res:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("event:"):
                        current_event_type = line_str[6:].strip()
                    elif line_str.startswith("data:"):
                        data_str = line_str[5:].strip()
                        if current_event_type == "heartbeat":
                            continue
                        try:
                            payload_json = json.loads(data_str)
                            print(f"\n[SSE EVENT] {current_event_type}:")
                            if current_event_type == "step_complete":
                                print(f"  Step: {payload_json.get('step')}")
                                step_data = payload_json.get("data", {})
                                if isinstance(step_data, dict):
                                    print(f"  Think Pad: {step_data.get('think_pad')}")
                                    print(f"  Response: {step_data.get('ai_response')}")
                                else:
                                    print(f"  Data: {step_data}")
                            elif current_event_type == "result":
                                state = payload_json.get("state", {})
                                print(f"  Final Response: {state.get('ai_response')}")
                                print(f"  Brief: {state.get('brief')}")
                            elif current_event_type == "step_start":
                                print(f"  Step: {payload_json.get('step')}")
                                print(f"  Message: {payload_json.get('message')}")
                            else:
                                print(f"  Raw Payload: {payload_json}")
                        except Exception as parse_err:
                            print(f"  Failed parsing JSON: {data_str} (error: {parse_err})")
                        current_event_type = None
        except Exception as sse_err:
            print(f"SSE error: {sse_err}")

    # Run the blocking read_sse in an executor
    await asyncio.get_event_loop().run_in_executor(None, read_sse)

if __name__ == "__main__":
    asyncio.run(main())
