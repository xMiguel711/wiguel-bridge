# Wiguel-AI Bridge

Wiguel-AI Bridge is a Python script that connects a local `llama.cpp` instance with the Wiguel-AI PWA interface. This allows you to leverage your local compute resources to run AI models while using a modern, synchronized UI.

## Prerequisites

1. **Python 3.8+** installed.
2. **`llama-server`** (from `llama.cpp`) installed.

## Setup Guide

### 1. Install Dependencies

You need to install the required Python libraries (`fastapi` and `uvicorn`).

- **Linux / macOS / Termux:**
  ```bash
  pip3 install fastapi uvicorn
  ```
- **Windows (PowerShell):**
  ```powershell
  pip install fastapi uvicorn
  ```

### 2. Run the Bridge

1. Download `wiguel-bridge.py` to your local folder.
2. Open your terminal or shell in that folder and run:

- **Linux / macOS / Termux:**
  ```bash
  python3 wiguel-bridge.py
  ```
- **Windows (PowerShell):**
  ```powershell
  python wiguel-bridge.py
  ```

### 3. Sync with Wiguel-AI

1. The script will automatically download the required GGUF model if not already present.
2. Once running, a unique **Synchronization PIN** will be displayed in your terminal.
3. Open the Wiguel-AI app in your browser at `https://wiguel-ai.vercel.app`.
4. Click the **Bridge** icon in the UI and enter the PIN shown in the terminal.
5. You are now connected! Your local machine is handling the AI processing.

## How it Works
When you successfully pair the Bridge using the PIN:
- **Request Routing:** Whenever you type a message in the Wiguel-AI interface, the PWA will securely forward the request to this local Python Bridge instead of the cloud API.
- **Local Processing:** The Bridge forwards the request to your local `llama-server`.
- **Real-time Responses:** The generated AI reply flows back through the Bridge to the Wiguel-AI UI, appearing immediately in the chat window, just as if you were communicating with a cloud service.

## Features
- **Automatic Model Download:** Downloads required models directly from HuggingFace.
- **Backend Integration:** Manages the `llama.cpp` server backend.
- **Sync PIN:** Secure connection mechanism for pairing UI and bridge.
- **LAN Sharing:** Allows other devices on your local network to connect to your AI instance.
