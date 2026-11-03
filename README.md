# WebShot 📸

A powerful web screenshotting tool for reconnaissance and security research.
WebShot is a Python-based web screenshotting tool built for penetration testers, bug bounty hunters, and security researchers to capture and visualize web assets efficiently.

# 🛠️ Installation
git clone https://github.com/mayankjangra2006/WebShot.git
cd WebShot

# Setup
1. Install Playwright
    -> pip install playwright
2. Install Chromium
    -> playwright install chromium
If the above command does not work, try:
    -> python -m playwright install chromium
3. Install system dependencies (Linux)
    -> sudo python -m playwright install-deps chromium

# 🚀 Usage
Create a text file containing your target URLs or hosts.

Example: targets.txt
https://example.com
https://google.com
https://github.com

# Run WebShot:
python3 webshot.py -i targets.txt -o results/ <br>
Replace the example command with the actual argument supported by your script.
<img width="1599" height="899" alt="image" src="https://github.com/user-attachments/assets/beeb54ef-0e36-47bc-bd87-3006e958c3e2" />


# 📸 Screenshots
<img width="525" height="304" alt="image" src="https://github.com/user-attachments/assets/d5267c66-6f5d-4535-8c4c-67ae804b47b8" />

-> After completion, a folder with the name you selected will be created.
<img width="941" height="322" alt="image" src="https://github.com/user-attachments/assets/6c1912ed-e67b-4c4c-b500-a1465e640776" />
-> Open report.html in your browser
<img width="1599" height="899" alt="image" src="https://github.com/user-attachments/assets/d7485ce2-7678-4656-ab46-0a3203853905" />
-> You will find all your screenshots with status code , image and clickable url

# 👨‍💻 Author
Created by Mayank Jangra<br>
If you find WebShot useful, consider giving the repository a ⭐

# 📄 License
This project is licensed under the MIT License. See LICENSE for details.
