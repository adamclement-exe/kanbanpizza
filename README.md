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
# Kanban Principles

The Kanban Pizza Game is an interactive exercise designed to immerse participants in the foundational principles of Kanban and Agile methodologies. Each round introduces specific challenges and learning opportunities that align with key Kanban practices and the principles outlined in the Agile Manifesto.

## Round 1: Introduction to Workflow Visualization

**Objective:** Produce as many correctly assembled pizzas as possible within a set timeframe.

**Learning Focus:**

- **Visualize the Workflow:** Participants begin by understanding the importance of visualizing tasks. In this round, the process of creating pizzas represents the workflow, making it essential to see and manage each step clearly.

- **Identify Process Bottlenecks:** By engaging in the pizza-making process, teams can observe where delays or inefficiencies occur, highlighting areas needing improvement.

**Agile Manifesto Alignment:** This round emphasizes "Individuals and interactions over processes and tools," encouraging collaboration and communication among team members.

## Round 2: Implementing Work-In-Progress (WIP) Limits

**Objective:** Introduce specific stations for each pizza-making step (e.g., dough preparation, topping addition, baking) and set limits on the number of pizzas in progress at each station.

**Learning Focus:**

- **Limit Work in Progress (WIP):** By restricting the number of pizzas at each station, participants experience how WIP limits help maintain a smooth workflow and prevent task overload.

- **Enhance Process Efficiency:** Teams learn that limiting WIP leads to faster completion times and higher quality outputs, as focus is maintained on fewer tasks simultaneously.

**Agile Manifesto Alignment:** This round supports the principle of "Simplicity—the art of maximizing the amount of work not done," by focusing on essential tasks and reducing unnecessary work.

## Round 3: Managing Flow and Continuous Improvement

**Objective:** Introduce customer orders with specific requirements and encourage teams to adapt their processes to meet these demands efficiently.

**Learning Focus:**

- **Manage Flow:** Participants must adapt to varying customer orders, learning to manage and optimize the flow of work to meet specific demands.

- **Continuous Improvement:** After each round, teams reflect on their performance, identify inefficiencies, and implement improvements, embodying the principle of continuous enhancement.

**Agile Manifesto Alignment:** This round reflects the principle of "At regular intervals, the team reflects on how to become more effective, then tunes and adjusts its behavior accordingly," promoting iterative learning and adaptation.


Through these progressive rounds, the Kanban Pizza Game effectively simulates the application of Kanban principles and Agile practices, providing participants with experiential learning that can be translated into real-world process improvements.

## Prerequisites
- Python 3.8+  
- Git  
- A web browser (Chrome, Firefox, etc.)
## Setup Instructions
1. **Clone the Repository**: ```bash git clone https://github.com/adamclement-exe/kanbanpizza.git && cd kanbanpizza```
2. **Create a Virtual Environment**: ```bash python -m venv venv```  
   - On Unix/Linux/Mac: ```bash source venv/bin/activate```  
   - On Windows: ```bash venv\Scripts\activate```
3. **Install Dependencies**: ```bash pip install -r requirements.txt```  
   Required packages: Flask, Flask-SocketIO, eventlet (or another async worker).
4. **Run the Application**: ```bash python app.py```
5. **Open your browser** to `http://localhost:5000`.
## How to Play
1. **Join a Room**: Enter a room name (or use "default") on the welcome screen.  
2. **Round 1**: Prepare ingredients (base, sauce, ham, pineapple) individually. Build and bake pizzas meeting specific criteria (1 base, 1 sauce, 4 ham or 2 ham + 2 pineapple).  
3. **Round 2**: Collaborate using shared builders to optimize production.  
4. **Round 3**: Fulfill 50 customer orders shown as Kanban cards (e.g., "Order: abc123", "🟡x1 🔴x1 🥓x4", "🍕🥓"). Match ingredients exactly to avoid waste.  
5. **Scoring**: Earn points for completed pizzas and fulfilled orders; lose points for waste or unmatched pizzas.
## Deployment on Render
This project is deployed on Render. To deploy your own instance:  
1. **Fork this Repository** to your GitHub account.  
2. **Create a New Web Service on Render**: Connect your forked repo. Set runtime to Python 3. Use this build command: ```bash pip install -r requirements.txt``` Use this start command: ```bash gunicorn -k eventlet -w 1 --timeout 120 --log-level debug app:app```  
3. **Environment Variables (optional)**: `SECRET_KEY`: Set a secure key (default: "secret!").  
4. **Deploy**: Render will build and deploy; access your URL (e.g., `your-app.onrender.com`).  
> **Note:** Render free tier may spin down after inactivity, causing a delay on first load. Threading is avoided for customer orders to ensure compatibility.
## Development
- **Backend**: Flask with SocketIO for real-time updates; SocketIO with polling as backup (during heavy loads) for Round 3 orders.  
- **Frontend**: HTML/CSS/JavaScript with Bootstrap for UI.
### Files:
- `kanbanpizza/static/` # CSS, JavaScript, and images  
- `kanbanpizza/templates/` # HTML templates  
- `kanbanpizza/app.py` # Main server logic  
- `kanbanpizza/requirements.txt` # Dependencies  
- `kanbanpizza/README.md` # Project documentation  
- `kanbanpizza/LICENSE` # License details
## How to Contribute
1. **Fork and clone the repo**.  
2. **Make changes** and test locally.  
3. **Submit a pull request**.
## Known Issues
- **Round 3 kanban cards on mobile** need to be wider to accomadate busy pizzas
- **Emoji overlay alignment** may vary slightly across browsers; tested on Chrome.   
## License
This project is open-source under the MIT License. Feel free to use, modify, and share!
