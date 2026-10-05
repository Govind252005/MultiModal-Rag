"""
Gemini key + model diagnostic.

Run from backend/ with your key:
    python diagnose_gemini.py AQ.xxxxxxxx
or set it in the environment first:
    $env:GEMINI_API_KEY="AQ.xxxx"; python diagnose_gemini.py

It (1) confirms the key authenticates, (2) lists every model your project can
actually use for generateContent, and (3) does a tiny real generation with the
model configured in config.py — printing the REAL error if anything fails.
"""
import os
import sys


def main() -> None:
    key = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GEMINI_API_KEY", "")).strip()
    if not key:
        print("No key provided. Pass it as an argument or set GEMINI_API_KEY.")
        sys.exit(1)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("google-genai is not installed. Run:  pip install google-genai")
        sys.exit(1)

    client = genai.Client(api_key=key)

    # 1. Auth check + list usable models -------------------------------------
    print("=" * 60)
    print("1. Authenticating and listing available models...")
    print("=" * 60)
    usable = []
    try:
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions or not actions:
                usable.append(m.name)
        print(f"✓ Key authenticated. {len(usable)} model(s) support generateContent:\n")
        for name in usable:
            print(f"   - {name}")
    except Exception as exc:
        print(f"✗ Key FAILED to authenticate.\n   Real error: {exc}")
        sys.exit(1)

    # 2. Try to actually generate with several candidate models ------------
    candidates = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
    ]

    print("\n" + "=" * 60)
    print("2. Testing which models can ACTUALLY generate (uses quota)...")
    print("=" * 60)

    working = []
    for model in candidates:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=[types.Part(text="Say hi in 3 words.")])],
                config=types.GenerateContentConfig(max_output_tokens=20),
            )
            print(f"   ✓ {model:<28} -> {resp.text!r}")
            working.append(model)
        except Exception as exc:
            msg = str(exc)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                reason = "no quota (429 / limit 0)"
            elif "NOT_FOUND" in msg or "404" in msg:
                reason = "model not available to this project"
            elif "PERMISSION_DENIED" in msg or "403" in msg:
                reason = "permission denied"
            else:
                reason = msg.split("\n")[0][:80]
            print(f"   ✗ {model:<28} -> {reason}")

    print("\n" + "=" * 60)
    if working:
        print(f"USE THIS MODEL: {working[0]}")
        print(f"Set it before starting the server:")
        print(f'   $env:GEMINI_MODEL="{working[0]}"')
    else:
        print("NO model can generate — your project has 0 generation quota.")
        print("Enable the free tier / billing for this project:")
        print("   https://aistudio.google.com/app/apikey  (check the project's billing)")
        print("   or create a key in a DIFFERENT project that has free-tier quota.")
    print("=" * 60)


if __name__ == "__main__":
    main()
