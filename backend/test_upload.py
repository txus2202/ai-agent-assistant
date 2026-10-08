import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        files = {'file': ('test.webm', b'dummy_audio_content', 'audio/webm')}
        resp = await client.post('http://localhost:8000/api/audio/transcribe', files=files)
        print(resp.status_code)
        print(resp.text)

asyncio.run(main())
