import asyncio
import sys
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.services.extract_content import extract_content_from_pdf

class RealFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.file = None
    
    async def read(self):
        with open(self.filepath, 'rb') as f:
            return f.read()
    
    async def seek(self, position):
        pass  

def chunk_text(text, max_chars=6000):
    """Split text into chunks that fit within token limits"""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_chars:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

async def summarize_chunk_with_gpt4(text_chunk, chunk_num, total_chunks, timeout=120):
    """Summarize a single chunk of text with timeout"""
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return None
    
    try:
        prompt = f"""
        This is chunk {chunk_num} of {total_chunks} from a document. Please provide a concise summary of this section.
        
        Text chunk:
        {text_chunk}
        
        Provide a brief summary focusing on the key points in this section.
        """
        
        async with AsyncOpenAI(api_key=api_key, timeout=timeout) as client:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.3
                ),
                timeout=timeout
            )
        return response.choices[0].message.content
        
    except asyncio.TimeoutError:
        print(f"Timeout error for chunk {chunk_num} after {timeout} seconds")
        return None
    except Exception as e:
        print(f"Error calling GPT-4 API for chunk {chunk_num}: {e}")
        return None

async def summarize_with_gpt4_with_retry(text, title, max_retries=3, base_timeout=120):
    """
    Summarize with retry logic and exponential backoff
    """
    last_error = None
    
    for attempt in range(max_retries):
        timeout = base_timeout * (2 ** attempt)  # 120s, 240s, 480s
        try:
            print(f"Attempt {attempt + 1}/{max_retries} with timeout {timeout}s")
            result = await summarize_with_gpt4(text, title, timeout=timeout)
            
            if result.get('summary'):
                return result
            else:
                last_error = result.get('message', 'Unknown error')
                
        except asyncio.TimeoutError:
            last_error = f"Request timed out after {timeout} seconds"
            print(f"Attempt {attempt + 1} timed out")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Wait before retry: 1s, 2s, 4s
        except Exception as e:
            last_error = str(e)
            print(f"Attempt {attempt + 1} failed with error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    
    return {
        "summary": None,
        "message": f"Failed after {max_retries} attempts. Last error: {last_error}",
        "used_tokens": 0
    }

async def summarize_with_gpt4(text, title, timeout=300):
    """Summarize the extracted text using GPT-4 with chunking for large documents"""
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        error_msg = "OPENAI_API_KEY not found in environment variables"
        print(f"Error: {error_msg}")
        return {"summary": None, "message": error_msg, "used_tokens": 0}
    
    try:
        total_tokens = 0
        
        if len(text) > 6000:
            print(f"Text is too long ({len(text)} characters). Splitting into chunks...")
            
            chunks = chunk_text(text)
            print(f"Split into {len(chunks)} chunks")
            
            chunk_summaries = []
            failed_chunks = []
            
            # Process chunks with individual timeouts
            for i, chunk in enumerate(chunks, 1):
                print(f"Summarizing chunk {i}/{len(chunks)}...")
                try:
                    chunk_summary = await summarize_chunk_with_gpt4(
                        chunk, i, len(chunks), timeout=timeout
                    )
                    if chunk_summary:
                        chunk_summaries.append(chunk_summary)
                    else:
                        failed_chunks.append(i)
                except Exception as e:
                    print(f"Failed to summarize chunk {i}: {e}")
                    failed_chunks.append(i)
            
            if not chunk_summaries:
                return {
                    "summary": None,
                    "message": "All chunks failed to summarize",
                    "used_tokens": 0
                }
            
            if failed_chunks:
                print(f"Warning: Failed to summarize chunks: {failed_chunks}")
            
            combined_summaries = "\n\n".join(chunk_summaries)
            
            print("Creating final comprehensive summary...")
            
            final_prompt = f"""
            Please provide a comprehensive summary of the document titled "{title}" based on these section summaries:
            
            {combined_summaries}
            
            Please provide:
            An executive summary of the document with one paragraph
            
            Format the summary in a clear, structured manner.
            """
            
            async with AsyncOpenAI(api_key=api_key, timeout=timeout) as client:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries of documents."},
                            {"role": "user", "content": final_prompt}
                        ],
                        max_tokens=1500,
                        temperature=0.3
                    ),
                    timeout=timeout
                )

            summary_content = response.choices[0].message.content
            total_tokens = response.usage.total_tokens

        else:
            prompt = f"""
            Please provide a comprehensive summary of the following document titled "{title}".
            
            Document content:
            {text}
            
            Please provide:
            An executive summary of the document with one paragraph
           
            Format the summary in a clear, structured manner.
            """
            
            print("Generating summary with GPT-4...")
            
            async with AsyncOpenAI(api_key=api_key, timeout=timeout) as client:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries of documents."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1500,
                        temperature=0.3
                    ),
                    timeout=timeout
                )
            
            summary_content = response.choices[0].message.content
            total_tokens = response.usage.total_tokens

        return {
            "summary": summary_content,
            "used_tokens": total_tokens,
            "message": "Success"
        }

    except asyncio.TimeoutError:
        error_msg = f"Request timed out after {timeout} seconds"
        print(f"Error: {error_msg}")
        return {"summary": None, "message": error_msg, "used_tokens": 0}
    except Exception as e:
        error_msg = f"Error calling GPT-4 API: {str(e)}"
        print(error_msg)
        return {"summary": None, "message": error_msg, "used_tokens": 0}

async def main():
    pdf_path = "app/data/provider-registration-policy.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return
    
    print(f"Reading PDF from: {pdf_path}")
    
    try:
        real_file = RealFile(pdf_path)
        text, title = await extract_content_from_pdf(real_file)
        
        print(f"Title: {title}")
        print(f"Extracted text length: {len(text)} characters")
        
        # Use the retry version for better reliability
        result = await summarize_with_gpt4_with_retry(text, title)
        
        if result.get('summary'):
            print("\n" + "="*80)
            print("SUMMARY:")
            print("="*80)
            print(result['summary'])
            print("="*80)
            print(f"\nTokens used: {result['used_tokens']}")
        else:
            print(f"Failed to generate summary: {result.get('message')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())