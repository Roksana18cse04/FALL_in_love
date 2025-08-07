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

async def summarize_chunk_with_gpt4(text_chunk, chunk_num, total_chunks):
    """Summarize a single chunk of text"""
    
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
        
        client = AsyncOpenAI(api_key=api_key)
        
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error calling GPT-4 API for chunk {chunk_num}: {e}")
        return None

async def summarize_with_gpt4(text, title):
    """Summarize the extracted text using GPT-4 with chunking for large documents"""
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return None
    
    try:
        if len(text) > 6000:
            print(f"Text is too long ({len(text)} characters). Splitting into chunks...")
            
            chunks = chunk_text(text)
            print(f"Split into {len(chunks)} chunks")
            
            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                print(f"Summarizing chunk {i}/{len(chunks)}...")
                chunk_summary = await summarize_chunk_with_gpt4(chunk, i, len(chunks))
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
            
            combined_summaries = "\n\n".join(chunk_summaries)
            
            print("Creating final comprehensive summary...")
            
            final_prompt = f"""
            Please provide a comprehensive summary of the document titled "{title}" based on these section summaries:
            
            {combined_summaries}
            
            Please provide:
            An executive summary of the document with one paragraph
            
            
            Format the summary in a clear, structured manner.
            """
            
            client = AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries of documents."},
                    {"role": "user", "content": final_prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
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
            
            client = AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries of documents."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error calling GPT-4 API: {e}")
        return None

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
        
        summary = await summarize_with_gpt4(text, title)
        
        if summary:
            print("\n" + "="*80)
            print("SUMMARY:")
            print("="*80)
            print(summary)
            print("="*80)
        else:
            print("Failed to generate summary.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 
