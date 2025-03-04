# Kanban Pizza 🍕

Kanban Pizza is a collaborative, multiplayer game that simulates a pizza-making workflow using Kanban principles. Built with Flask and SocketIO, it runs as a web application where players work together to prepare ingredients, build pizzas, and fulfill customer orders across three rounds of increasing complexity.

Play it live at: [kanbanpizza.onrender.com](https://kanbanpizza.onrender.com)

## Features
- **Three Rounds**:
  - **Round 1**: Individual pizza building with simple rules (e.g., 1 base, 1 sauce, 4 ham or 2 ham + 2 pineapple).
  - **Round 2**: Collaborative building using shared pizza builders.
  - **Round 3**: Match 50 customer orders with varied ingredient combos, displayed as Kanban cards.
- **Real-Time Gameplay**: SocketIO enables live updates for all players in a room.
- **Kanban Cards**: In Round 3, orders appear as cards with ID, ingredients (e.g., 🟡x1 🔴x1 🥓x4), and pizza emoji (e.g., 🍕🥓).
- **Scoring**: Points based on completed pizzas, fulfilled orders, and penalties for waste.

## Prerequisites
- Python 3.8+
- Git
- A web browser (Chrome, Firefox, etc.)

## Setup Instructions
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/adamclement-exe/kanbanpizza.git
   cd kanbanpizza
   ```
2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   ```
   - On Unix/Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   Required packages: Flask, Flask-SocketIO, eventlet (or another async worker).
4. **Run the Application**:
   ```bash
   python app.py
   ```
5. **Open your browser** to `http://localhost:5000`.

## How to Play
1. **Join a Room**: Enter a room name (or use "default") on the welcome screen.
2. **Round 1**:
   - Prepare ingredients (base, sauce, ham, pineapple) individually.
   - Build and bake pizzas meeting specific criteria (1 base, 1 sauce, 4 ham or 2 ham + 2 pineapple).
3. **Round 2**:
   - Collaborate using shared builders to optimize production.
4. **Round 3**:
   - Fulfill 50 customer orders shown as Kanban cards (e.g., "Order: abc123", "🟡x1 🔴x1 🥓x4", "🍕🥓").
   - Match ingredients exactly to avoid waste.
5. **Scoring**: Earn points for completed pizzas and fulfilled orders; lose points for waste or unmatched pizzas.

## Deployment on Render
This project is deployed on Render. To deploy your own instance:

1. **Fork this Repository** to your GitHub account.
2. **Create a New Web Service on Render**:
   - Connect your forked repo.
   - Set runtime to Python 3.
   - Use this build command:
     ```bash
     pip install -r requirements.txt
     ```
   - Use this start command:
     ```bash
     gunicorn -k eventlet -w 1 --timeout 120 --log-level debug main:app
     ```
3. **Environment Variables (optional)**:
   - `SECRET_KEY`: Set a secure key (default: "secret!").
4. **Deploy**: Render will build and deploy; access your URL (e.g., `your-app.onrender.com`).

> **Note:** Render free tier may spin down after inactivity, causing a delay on first load. Threading is avoided for customer orders to ensure compatibility.

## Development
- **Backend**: Flask with SocketIO for real-time updates; polling for Round 3 orders.
- **Frontend**: HTML/CSS/JavaScript with Bootstrap for UI.

### Files:
```
kanbanpizza/
├── static/              # CSS, JavaScript, and images
├── templates/           # HTML templates
├── app.py               # Main server logic
├── requirements.txt     # Dependencies
├── README.md            # Project documentation
└── LICENSE              # License details
```

## How to Contribute
1. **Fork and clone the repo**.
2. **Make changes** and test locally.
3. **Submit a pull request**.

## Known Issues
- **Emoji overlay alignment** may vary slightly across browsers; tested on Chrome.
- **Render may log `[Errno 9] Bad file descriptor`** on shutdown, mitigated with graceful exit handling.

## License
This project is open-source under the MIT License. Feel free to use, modify, and share!

## How to Use
### Create the File Locally:
1. Open a text editor (e.g., VS Code, Notepad).
2. Copy the entire content from the code block above.
3. Paste it into a new file named `README.md` in your `kanbanpizza` directory.
4. Save the file.
5. Add, commit, and push to GitHub:
   ```bash
   git add README.md
   git commit -m "Add README for Kanban Pizza"
   git push origin main
   ```



