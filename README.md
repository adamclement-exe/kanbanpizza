
# Kanban Pizza 🍕
Kanban Pizza is a collaborative, multiplayer game that simulates a pizza-making workflow using Kanban principles. Built with Flask and SocketIO, it runs as a web application where players work together to prepare ingredients, build pizzas, and fulfill customer orders across three rounds of increasing complexity.  
Play it live at: [kanbanpizza.onrender.com](https://kanbanpizza.onrender.com)

Folow for news at [@kanbanpizza](https://mastodon.social/@kanbanpizza)

![game gif](https://github.com/adamclement-exe/kanbanpizza/blob/main/static/1.gif?raw=true)
## Features
- **Three Rounds**:  
  - **Round 1**: Individual pizza building with simple rules (e.g., 1 base, 1 sauce, 4 ham or 2 ham + 2 pineapple).  
  - **Round 2**: Collaborative building using shared pizza builders.  
  - **Round 3**: Match 15 customer orders with varied ingredient combos, displayed as Kanban cards.
    
- **Real-Time Gameplay**: SocketIO enables live updates for all players in a room.
    
- **Scoring**: Points based on completed pizzas, fulfilled orders, with penalties for waste.
  
- **Lead Time Tracking & Debrief Charts**:  
  - Every ingredient is timestamped at production.
  - When a pizza is built, the earliest ingredient timestamp is used as its build start time; the pizza’s completion time is recorded and a lead time (completion minus start time) is calculated.
  - During the debrief phase, a chart is displayed; a line chart showing each pizza's lead time.

# Kanban/Agile Principles

| Round | Description | Kanban Principles | Agile Principles |
|-------|-------------|-------------------|------------------|
| **1** | **Workflow Visualization and WIP Limits**<br>Teams visualize their workflow and implement Work-In-Progress (WIP) limits to optimize production. | - Visualize the workflow<br>- Limit Work in Progress (WIP) | - Simplicity—the art of maximizing the amount of work not done<br>- Continuous attention to technical excellence |
| **2** | **Enhanced Collaboration**<br>Teams utilize shared pizza builders, emphasizing collaboration to improve efficiency and quality. | - Manage flow<br>- Make process policies explicit | - Individuals and interactions over processes and tools<br>- Business people and developers must work together daily throughout the project |
| **3** | **Customer Orders and Flow Management**<br>Teams handle specific customer orders, adapting their processes to manage flow and meet customer demands effectively. | - Implement feedback loops<br>- Improve collaboratively and experimentally | - Responding to change over following a plan<br>- At regular intervals, the team reflects on how to become more effective, then tunes and adjusts its behavior accordingly |

## Prerequisites
- Python 3.8+  
- Git  
- A web browser (Chrome, Firefox, etc.)

## Setup Instructions
1. **Clone the Repository**:  
   `git clone https://github.com/adamclement-exe/kanbanpizza.git && cd kanbanpizza`
2. **Create a Virtual Environment**:  
   `python -m venv venv`  
   - On Unix/Linux/Mac: `source venv/bin/activate`  
   - On Windows: `venv\Scripts\activate`
3. **Install Dependencies**:  
   `pip install -r requirements.txt`  
   Required packages: Flask, Flask-SocketIO, eventlet (or another async worker).
4. **Run the Application**:  
   `python app.py`
5. **Open your browser** to `http://localhost:5000`.

## How to Play
1. **Join a Room**: Enter a room name and password on the welcome screen.
2. **Round 1**: Prepare ingredients (base, sauce, ham, pineapple) individually. Build and bake pizzas meeting specific criteria (1 base, 1 sauce, 4 ham or 2 ham + 2 pineapple).
3. **Round 2**: Collaborate using shared builders to optimize production.
4. **Round 3**: Fulfill 50 customer orders shown as Kanban cards (e.g., "Order: abc123", "🟡x1 🔴x1 🥓x4", "🍕🥓"). Match ingredients exactly to avoid waste.
5. **Debrief Phase**: After rounds end, a debrief session displays a chart showing each pizza’s lead time (calculated from the earliest ingredient produced).
6. **Scoring**: Earn points for completed pizzas and fulfilled orders; lose points for waste or unmatched pizzas.

## Deployment on Render
This project is deployed on Render. To deploy your own instance:
1. **Fork this Repository** to your GitHub account.
2. **Create a New Web Service on Render**: Connect your forked repo. Set runtime to Python 3. Use this build command:  
   `pip install -r requirements.txt`  
   Use this start command:  
   `python wsgi.py`
3. **Environment Variables (optional)**: Set `SECRET_KEY` to a secure key (default: "secret!").
4. **Deploy**: Render will build and deploy; access your URL (e.g., `your-app.onrender.com`).

> **Note:** Render free tier may spin down after inactivity, causing a delay on first load. Threading is avoided for customer orders to ensure compatibility.

## Development
- **Backend**: Flask with SocketIO for real-time updates; SocketIO (with polling as backup) is used during heavy loads (especially in Round 3).
- **Frontend**: HTML/CSS/JavaScript with Bootstrap for UI.
  
### Files:
- `kanbanpizza/static/` – CSS, JavaScript, and images  
- `kanbanpizza/templates/` – HTML templates  
- `kanbanpizza/wsgi.py` – Launcher code  
- `kanbanpizza/app.py` – Main server logic  
- `kanbanpizza/requirements.txt` – Dependencies  
- `kanbanpizza/README.md` – Project documentation  
- `kanbanpizza/LICENSE` – License details

## How to Contribute
1. **Fork and clone the repo**.
2. **Make changes** and test locally.
3. **Submit a pull request**.

## Known Issues
- **Round 3 Kanban Cards on Mobile**: May need wider cards to accommodate busy pizzas.
- **Emoji Overlay Alignment**: May vary slightly across browsers (tested on Chrome).

## License
This project is open-source under the MIT License. Feel free to use, modify, and share!
