from pathlib import Path

def load_Document(file_path):
    with open(file_path,"r",encoding="utf-8") as file:
        return file.read()

def create_Chunk(text,chunks_size=300):
    words = text.split()
    chunks=[]
    for i in range(0,len(words),chunks_size):
        chunk=" ".join(words[i:i+chunks_size])
        chunks.append(chunk)
    return chunks

if __name__=="__main__":
    file_path = Path("rag/documents/leave_policy.txt")
    text=load_Document(file_path)
    chunks=create_Chunk(text)
    print("\nTotal Chunks:", len(chunks))
    for i, chunk in enumerate(chunks, start=1):
        print(f"\n--- Chunk {i} ---")
        print(chunk)