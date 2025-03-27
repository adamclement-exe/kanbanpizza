    var socket = io({ transports: ['websocket', 'polling'], reconnection: true });
    var myRoom = localStorage.getItem('myRoom') || "";
    var isInitialConnect = true;

    // Swear filter using Purgomalum API
    async function checkProfanity(text) {
      try {
        const response = await fetch(`https://www.purgomalum.com/service/containsprofanity?text=${encodeURIComponent(text)}`);
        const containsProfanity = await response.text();
        return containsProfanity === 'true';
      } catch (error) {
        console.error('Profanity check failed:', error);
        return false; // Fallback: Assume no profanity if API fails
      }
    }

async function filterRoomName(event) {
  event.preventDefault();
  const roomInput = document.getElementById("room-input");
  const passwordInput = document.getElementById("password-input"); // Add this input in HTML
  const feedback = document.getElementById("room-input-feedback");
  const roomName = roomInput.value.trim();
  const password = passwordInput.value.trim();

  if (!roomName || !password) {
    roomInput.classList.add("is-invalid");
    feedback.textContent = "Room name and password cannot be empty.";
    return;
  }

  const hasProfanity = await checkProfanity(roomName);
  if (hasProfanity) {
    roomInput.classList.add("is-invalid");
    feedback.textContent = "Room name contains inappropriate language.";
    return;
  }

  roomInput.classList.remove("is-invalid");
  feedback.textContent = "";
  myRoom = roomName;
  localStorage.setItem('myRoom', myRoom);
  socket.emit('join', { room: myRoom, password: password });
}

socket.on('connect', function() {
  if (isInitialConnect) {
    var roomModal = new bootstrap.Modal(document.getElementById('roomModal'), {
      backdrop: 'static',
      keyboard: false
    });
    roomModal.show();
    socket.emit('request_room_list');
    isInitialConnect = false;
  } else if (myRoom) {
    const password = localStorage.getItem('myRoomPassword') || prompt("Enter the password for room " + myRoom);
    if (password) {
      localStorage.setItem('myRoomPassword', password);
      socket.emit('join', { room: myRoom, password: password });
      console.log("Reconnecting to room:", myRoom);
    }
  }
});


    socket.on('disconnect', function() {
      console.log("Disconnected from server");
      updateMessage("Disconnected. Attempting to reconnect...");
    });

    socket.on('reconnect', function() {
      console.log("Reconnected to server");
      updateMessage("Reconnected to room " + myRoom);
    });

    document.getElementById("join-form").addEventListener("submit", filterRoomName);

    var builderIngredients = [];
    var touchSelectedIngredient = null;
    var ingredientEmoji = {
      "base": "🟡",
      "sauce": "🔴",
      "ham": "🥓",
      "pineapple": "🍍"
    };
    var orderEmoji = {
      "ham": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span></div>',
      "pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍</span></div>',
      "ham & pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span><span class="emoji">🍍</span></div>',
      "light ham": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span></div>',
      "light pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍</span></div>',
      "plain": '<div class="emoji-wrapper"><span class="emoji">🍕</span></div>',
      "heavy ham": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span></div>',
      "heavy pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍</span></div>'
    };

    const debriefContent = {
      1: {
        question: "Reflect on the round: How did you identify and streamline your pizza-making process? Did the oven’s WIP limit of 3 pizzas affect your strategy?",
        quote: "“Working software is the primary measure of progress.” – Agile Manifesto. In this case, think of 'working software' as successfully baked pizzas!"
      },
      2: {
        question: "Reflect on the round: How did collaboration with your team impact your pizza production? Did sharing builders help or hinder your flow?",
        quote: "“Individuals and interactions over processes and tools.” – Agile Manifesto. Collaboration is key to adapting and improving!"
      },
      3: {
        question: "Reflect on the round: How did customer orders change your priorities? Were you able to balance order fulfillment with minimizing waste?",
        quote: "“Customer collaboration over contract negotiation.” – Agile Manifesto. Meeting customer needs drives success!"
      }
    };

    function updateMessage(text) {
      document.querySelector("#messages .content").innerText = text;
    }

    function updateRoomLabels(room, playerCount) {
      document.getElementById("room-name-label").innerText = `${room}`;
      document.getElementById("player-count-label").innerText = `${playerCount}`;
    }

    setInterval(() => {
      socket.emit('time_request');
    }, 1000);

socket.on('room_list', function(data) {
  var tbody = document.getElementById('room-table-body');
  tbody.innerHTML = '';

  var rooms = Object.keys(data.rooms);
  if (rooms.length === 0) {
    var row = document.createElement('tr');
    var cell = document.createElement('td');
    cell.colSpan = 2;
    cell.innerText = 'No rooms active';
    row.appendChild(cell);
    tbody.appendChild(row);
  } else {
    rooms.forEach(function(room) {
      var row = document.createElement('tr');
      var nameCell = document.createElement('td');
      nameCell.innerText = room;
      var countCell = document.createElement('td');
      countCell.innerText = data.rooms[room];
      row.appendChild(nameCell);
      row.appendChild(countCell);
      tbody.appendChild(row);
    });
  }

  // Display high scores in a table
  var scoresDiv = document.getElementById('high-scores');
  scoresDiv.innerHTML = '<h3>Top Scores</h3>';

  // Create table
  var table = document.createElement('table');
  table.className = 'table table-bordered';

  // Table header
  var thead = document.createElement('thead');
  thead.innerHTML = `
    <tr>
      <th>Round</th>
      <th>1st</th>
      <th>2nd</th>
      <th>3rd</th>
    </tr>
  `;
  table.appendChild(thead);

  // Table body
  var tbody = document.createElement('tbody');
  for (let round = 1; round <= 3; round++) {
    var row = document.createElement('tr');

    // Round column
    var roundCell = document.createElement('td');
    roundCell.innerText = `Round ${round}`;
    row.appendChild(roundCell);

    // 1st, 2nd, 3rd columns
    for (let rank = 1; rank <= 3; rank++) {
      var rankCell = document.createElement('td');
      var scoreData = data.high_scores[round][rank];
      if (scoreData && scoreData.room_name) {
        rankCell.innerText = `${scoreData.room_name} (${scoreData.score})`;
      } else {
        rankCell.innerText = 'No Teams logged yet';
      }
      row.appendChild(rankCell);
    }

    tbody.appendChild(row);
  }
  table.appendChild(tbody);

  scoresDiv.appendChild(table);
});
socket.on('join_error', function(data) {
  const roomInput = document.getElementById("room-input");
  const passwordInput = document.getElementById("password-input");
  const roomFeedback = document.getElementById("room-input-feedback");
  const passwordFeedback = document.getElementById("password-input-feedback");

  if (data.message.includes("password")) {
    passwordInput.classList.add("is-invalid");
    passwordFeedback.textContent = data.message;
  } else {
    roomInput.classList.add("is-invalid");
    roomFeedback.textContent = data.message;
  }
});

    socket.on('game_state', function(newState) {
      updateGameState(newState);
      var joinModal = bootstrap.Modal.getInstance(document.getElementById('roomModal'));
      if (joinModal) {
        joinModal.hide();
      }
    });

    var modalEl = document.getElementById("modal");
    var modal = new bootstrap.Modal(modalEl);
    document.getElementById("instructions-btn").addEventListener("click", () => modal.show());
    document.getElementById("instructions-btn0").addEventListener("click", () => modal.show());
    document.getElementById("modal-close").addEventListener("click", () => modal.hide());

    socket.on('time_response', function(data) {
      if (data.phase === "debrief") {
        document.getElementById("timer").innerText = "DEBRIEF:\n" + data.roundTimeRemaining + " sec";
      } else if (data.phase === "round") {
        document.getElementById("timer").innerText = "Round Time:\n" + data.roundTimeRemaining + " sec";
      } else {
        document.getElementById("timer").innerText = "Round Time:";
      }
      document.getElementById("oven-timer").innerText = "Oven Time:\n" + data.ovenTime + " sec";
    });

    function allowDrop(ev) { ev.preventDefault(); }
    function drag(ev) {
      ev.dataTransfer.setData("ingredient_id", ev.target.getAttribute("data-id"));
      ev.dataTransfer.setData("ingredient_type", ev.target.dataset.type);
    }
function dropToBuilder(ev) {
    ev.preventDefault();
    var ingredient_id = ev.dataTransfer.getData("ingredient_id");
    var ingredient_type = ev.dataTransfer.getData("ingredient_type");
    socket.emit('take_ingredient', { ingredient_id: ingredient_id });
    if (state.round === 1) {
        builderIngredients.push({ id: ingredient_id, type: ingredient_type }); // Still for UI
        updateBuilderDisplay();
    }
}

document.getElementById("submit-pizza").addEventListener("click", function() {
    if (state.round === 1 && builderIngredients.length === 0) {
        alert("No ingredients selected for pizza!");
        return;
    }
    socket.emit('build_pizza', {}); // No ingredients needed; server knows them
    builderIngredients = []; // Clear local UI state
    updateBuilderDisplay();
});

    function dropToSharedBuilder(ev, sid) {
      ev.preventDefault();
      var ingredient_id = ev.dataTransfer.getData("ingredient_id");
      var ingredient_type = ev.dataTransfer.getData("ingredient_type");
      socket.emit('take_ingredient', { ingredient_id: ingredient_id, target_sid: sid });
    }
    function updateBuilderDisplay() {
      var builderDiv = document.getElementById("pizza-builder");
      builderDiv.innerHTML = "";
      builderIngredients.forEach(function(ing) {
        var item = document.createElement("div");
        item.classList.add("ingredient");
        item.innerText = ingredientEmoji[ing.type] || ing.type;
        builderDiv.appendChild(item);
      });
    }
    function prepareIngredient(type) {
      socket.emit('prepare_ingredient', { ingredient_type: type });
    }

    function renderPizzaBuilders(players) {
      var container = document.getElementById("pizza-builders-container");
      container.innerHTML = "";
      Object.keys(players).forEach(function(sid, index) {
        var colDiv = document.createElement("div");
        colDiv.classList.add("col-md-4");
        var builderDiv = document.createElement("div");
        builderDiv.classList.add("pizza-builder-container");
        builderDiv.innerHTML = `<h5>Builder #${index + 1}</h5>`;
        var ingredientsDiv = document.createElement("div");
        ingredientsDiv.classList.add("d-flex", "flex-wrap", "pizza-builder-dropzone");
        ingredientsDiv.setAttribute("ondrop", `dropToSharedBuilder(event, '${sid}')`);
        ingredientsDiv.setAttribute("ondragover", "allowDrop(event)");
        players[sid]["builder_ingredients"].forEach(function(ing) {
          var item = document.createElement("div");
          item.classList.add("ingredient");
          item.innerText = ingredientEmoji[ing.type] || ing.type;
          ingredientsDiv.appendChild(item);
        });
        builderDiv.appendChild(ingredientsDiv);
        var submitBtn = document.createElement("button");
        submitBtn.className = "btn btn-primary btn-custom mt-2";
        submitBtn.innerText = "Submit Pizza";
        submitBtn.onclick = function() {
          socket.emit('build_pizza', { player_sid: sid });
        };
        builderDiv.appendChild(submitBtn);
        colDiv.appendChild(builderDiv);
        container.appendChild(colDiv);

        if ('ontouchstart' in window) {
          ingredientsDiv.addEventListener("touchend", function(ev) {
            ev.preventDefault();
            if (touchSelectedIngredient) {
              socket.emit('take_ingredient', { ingredient_id: touchSelectedIngredient.id, target_sid: sid });
              touchSelectedIngredient = null;
              var selectedItems = document.querySelectorAll('.ingredient.selected');
              selectedItems.forEach(function(el) {
                el.classList.remove('selected');
              });
            }
          });
        }
      });
    }



    if ('ontouchstart' in window) {
      var builderDiv = document.getElementById("pizza-builder");
      builderDiv.addEventListener("touchend", function(ev) {
        ev.preventDefault();
        if (touchSelectedIngredient && state.round === 1) {
          socket.emit('take_ingredient', { ingredient_id: touchSelectedIngredient.id });
          builderIngredients.push({ id: touchSelectedIngredient.id, type: touchSelectedIngredient.type });
          updateBuilderDisplay();
          var selectedItems = document.querySelectorAll('.ingredient.selected');
          selectedItems.forEach(function(el) {
            el.classList.remove('selected');
          });
          touchSelectedIngredient = null;
        }
      });
    }

    var state = {};
    function updateGameState(newState) {
      state = newState;
      console.log("Game State:", state);

      const playerCount = Object.keys(state.players).length;
      updateRoomLabels(myRoom || "Unknown", playerCount);
      if (state.lead_times) {
            prepareChartData(state.lead_times);
        }
      if (state.current_phase === "round") {
        document.getElementById("game-area").style.display = "block";
        document.getElementById("start-round").style.display = "none";
      } else {
        document.getElementById("game-area").style.display = "none";
        document.getElementById("start-round").style.display = "inline-block";
      }

      updateVisibility();

      var ordersDiv = document.getElementById("customer-orders");
      var ordersList = document.getElementById("orders-list");
      var orderCount = document.getElementById("order-count");
      if (state.round === 3 && state.current_phase === "round") {
        ordersDiv.style.display = "block";
        ordersList.innerHTML = "";
        state.customer_orders.forEach(function(order) {
          var card = document.createElement("div");
          card.classList.add("order-card");
          card.setAttribute("data-order-id", order.id);

          var idDiv = document.createElement("div");
          idDiv.classList.add("order-id");
          idDiv.innerText = `Order: ${order.id.slice(0, 6)}`;
          card.appendChild(idDiv);

          var ingredientsDiv = document.createElement("div");
          ingredientsDiv.classList.add("order-ingredients");
          var ingredientsText = [];
          if (order.ingredients.base > 0) ingredientsText.push(`${ingredientEmoji["base"]}x${order.ingredients.base}`);
          if (order.ingredients.sauce > 0) ingredientsText.push(`${ingredientEmoji["sauce"]}x${order.ingredients.sauce}`);
          if (order.ingredients.ham > 0) ingredientsText.push(`${ingredientEmoji["ham"]}x${order.ingredients.ham}`);
          if (order.ingredients.pineapple > 0) ingredientsText.push(`${ingredientEmoji["pineapple"]}x${order.ingredients.pineapple}`);
          ingredientsDiv.innerText = ingredientsText.join(" ");
          card.appendChild(ingredientsDiv);

          var emojiDiv = document.createElement("div");
          emojiDiv.classList.add("order-emoji");
          emojiDiv.innerHTML = orderEmoji[order.type] || '<div class="emoji-wrapper"><span class="emoji">🍕</span></div>';
          card.appendChild(emojiDiv);

          ordersList.appendChild(card);
        });
        orderCount.innerText = state.customer_orders.length;
      } else {
        ordersDiv.style.display = "none";
        orderCount.innerText = "0";
      }

      var poolDiv = document.getElementById("prepared-pool");
      poolDiv.innerHTML = "";
      state.prepared_ingredients.forEach(function(item) {
        var div = document.createElement("div");
        div.classList.add("ingredient");
        div.setAttribute("draggable", "true");
        div.setAttribute("data-id", item.id);
        div.dataset.type = item.type;
        div.innerText = ingredientEmoji[item.type] || item.type;
        div.addEventListener("dragstart", drag);
        if ('ontouchstart' in window) {
          div.addEventListener("touchstart", function(ev) {
            ev.preventDefault();
            var previouslySelected = document.querySelectorAll('.ingredient.selected');
            previouslySelected.forEach(function(el) {
              el.classList.remove('selected');
            });
            touchSelectedIngredient = { id: item.id, type: item.type };
            div.classList.add("selected");
          });
        }
        poolDiv.appendChild(div);
      });

      function renderPizza(pizza, extraLabel) {
        var div = document.createElement("div");
        if (pizza.emoji) {
          div.innerHTML = pizza.emoji;
        } else {
          div.innerText = "Pizza " + pizza.pizza_id;
        }
        if (extraLabel) {
          var label = document.createElement("span");
          label.innerText = extraLabel;
          div.appendChild(label);
        }
        if (pizza.status) {
          div.classList.add(pizza.status);
        }
        return div;
      }

      var builtDiv = document.getElementById("built-pizzas");
      builtDiv.innerHTML = "";
      state.built_pizzas.forEach(function(pizza) {
        var div = renderPizza(pizza, "");
        var btn = document.createElement("button");
        btn.className = "btn btn-sm btn-outline-primary ms-2";
        btn.innerText = "Move to Oven";
        btn.onclick = function() {
          socket.emit('move_to_oven', { pizza_id: pizza.pizza_id });
        };
        div.appendChild(btn);
        builtDiv.appendChild(div);
      });

      var ovenDiv = document.getElementById("oven");
      ovenDiv.innerHTML = "";
      state.oven.forEach(function(pizza) {
        var div = renderPizza(pizza, " ");
        ovenDiv.appendChild(div);
      });

      var compDiv = document.getElementById("completed");
      compDiv.innerHTML = "";
      state.completed_pizzas.forEach(function(pizza) {
        var div = renderPizza(pizza, " ");
        compDiv.appendChild(div);
      });

      var wastedDiv = document.getElementById("wasted");
      wastedDiv.innerHTML = "";
      state.wasted_pizzas.forEach(function(pizza) {
        var div = renderPizza(pizza, "");
        wastedDiv.appendChild(div);
      });
    }

    function updateVisibility() {
      const pizzaBuilder = document.getElementById("pizza-builder");
      const submitPizza = document.getElementById("submit-pizza");
      const buildersContainer = document.getElementById("pizza-builders-container");
      const builderHeading = document.getElementById("builder-heading");

      if (state.round >= 1 && state.current_phase === "debrief" && state.round < state.max_rounds) {
        console.log("Debrief after Round 1 or 2: Showing shared builders");
        pizzaBuilder.style.display = "none";
        submitPizza.style.display = "none";
        buildersContainer.style.display = "flex";
        builderHeading.innerText = "Shared Pizza Builders";
        renderPizzaBuilders(state.players);
      } else if (state.round > 1) {
        console.log("Round 2+: Showing shared builders");
        pizzaBuilder.style.display = "none";
        submitPizza.style.display = "none";
        buildersContainer.style.display = "flex";
        builderHeading.innerText = "Shared Pizza Builders";
        if (state.current_phase === "round") {
          renderPizzaBuilders(state.players);
        }
      } else {
        console.log("Round 1 or waiting: Showing pizza-builder");
        pizzaBuilder.style.display = "flex";
        submitPizza.style.display = "inline-block";
        buildersContainer.style.display = "none";
        builderHeading.innerText = "Your Pizza Builder";
      }
    }

    socket.on('round_started', function(data) {
      state.round = data.round;
      state.current_phase = "round";
      state.customer_orders = data.customer_orders;
      updateMessage("Round " + data.round + " started. Duration: " + data.duration + " sec");
      document.getElementById("game-area").style.display = "block";
      document.getElementById("start-round").style.display = "none";
      var debriefModalEl = document.getElementById('debriefModal');
      var debriefModal = bootstrap.Modal.getInstance(debriefModalEl);
      if (debriefModal) {
        debriefModal.hide();
      }
      updateGameState(state);
    });

    socket.on('round_ended', function(result) {
      document.getElementById("debrief-pizzas-completed").innerText = result.completed_pizzas_count;
      document.getElementById("debrief-pizzas-wasted").innerText = result.wasted_pizzas_count;
      document.getElementById("debrief-pizzas-unsold").innerText = result.unsold_pizzas_count;
      document.getElementById("debrief-ingredients-left").innerText = result.ingredients_left_count || 0;
      document.getElementById("debrief-score").innerText = result.score;
      if (result.lead_times) {
        prepareChartData(result.lead_times);
        }
      if (state.round === 3) {
        document.getElementById("fulfilled-orders").style.display = "block";
        document.getElementById("remaining-orders").style.display = "block";
        document.getElementById("unmatched-pizzas").style.display = "block";
        document.getElementById("debrief-fulfilled-orders").innerText = result.fulfilled_orders_count || 0;
        document.getElementById("debrief-remaining-orders").innerText = result.remaining_orders_count || 0;
        document.getElementById("debrief-unmatched-pizzas").innerText = result.unmatched_pizzas_count || 0;
      } else {
        document.getElementById("fulfilled-orders").style.display = "none";
        document.getElementById("remaining-orders").style.display = "none";
        document.getElementById("unmatched-pizzas").style.display = "none";
      }

      const content = debriefContent[state.round] || {
        question: "Reflect on the round.",
        quote: "“Continuous improvement is better than delayed perfection.” – Agile principle."
      };
      document.getElementById("debrief-question").innerText = content.question;
      document.getElementById("debrief-quote").innerText = content.quote;

      var debriefModal = new bootstrap.Modal(document.getElementById('debriefModal'), {});
      debriefModal.show();
      updateVisibility();
    });

    socket.on('game_reset', function(state) {
      updateMessage("Round reset. Ready for a new round.");
      document.getElementById("timer").innerText = "Round Time:";
      document.getElementById("start-round").style.display = "inline-block";
      var debriefModalEl = document.getElementById('debriefModal');
      var modalInstance = bootstrap.Modal.getInstance(debriefModalEl);
      if (modalInstance) {
        modalInstance.hide();
      }
      updateGameState(state);
    });

    socket.on('ingredient_prepared', function(item) {
      updateMessage("Ingredient prepared: " + (ingredientEmoji[item.type] || item.type));
    });
    socket.on('build_error', function(data) {
      updateMessage("Build Error: " + data.message);
    });
    socket.on('pizza_built', function(pizza) {
      updateMessage("Pizza built: " + pizza.pizza_id);
    });
    socket.on('oven_error', function(data) {
      updateMessage("Oven Error: " + data.message);
    });
    socket.on('pizza_moved_to_oven', function(pizza) {
      updateMessage("Pizza moved to oven: " + pizza.pizza_id);
    });
    socket.on('oven_toggled', function(data) {
      updateMessage((data.state === "on") ? "Oven turned ON." : "Oven turned OFF.");
      var ovenContainer = document.getElementById("oven-container");
      if (data.state === "on") {
        ovenContainer.classList.add("oven-active");
      } else {
        ovenContainer.classList.remove("oven-active");
      }
    });
    socket.on('clear_shared_builder', function(data) {
      renderPizzaBuilders(state.players);
    });
    socket.on('new_order', function(order) {
      updateMessage("New order received: " + order.type);
      state.customer_orders.push(order);
      var ordersList = document.getElementById("orders-list");
      var card = document.createElement("div");
      card.classList.add("order-card");
      card.setAttribute("data-order-id", order.id);

      var idDiv = document.createElement("div");
      idDiv.classList.add("order-id");
      idDiv.innerText = `Order: ${order.id.slice(0, 6)}`;
      card.appendChild(idDiv);

      var ingredientsDiv = document.createElement("div");
      ingredientsDiv.classList.add("order-ingredients");
      var ingredientsText = [];
      if (order.ingredients.base > 0) ingredientsText.push(`${ingredientEmoji["base"]}x${order.ingredients.base}`);
      if (order.ingredients.sauce > 0) ingredientsText.push(`${ingredientEmoji["sauce"]}x${order.ingredients.sauce}`);
      if (order.ingredients.ham > 0) ingredientsText.push(`${ingredientEmoji["ham"]}x${order.ingredients.ham}`);
      if (order.ingredients.pineapple > 0) ingredientsText.push(`${ingredientEmoji["pineapple"]}x${order.ingredients.pineapple}`);
      ingredientsDiv.innerText = ingredientsText.join(" ");
      card.appendChild(ingredientsDiv);

      var emojiDiv = document.createElement("div");
      emojiDiv.classList.add("order-emoji");
      emojiDiv.innerHTML = orderEmoji[order.type] || '<div class="emoji-wrapper"><span class="emoji">🍕</span></div>';
      card.appendChild(emojiDiv);

      ordersList.appendChild(card);
      document.getElementById("order-count").innerText = state.customer_orders.length;
    });
    socket.on('order_fulfilled', function(data) {
      updateMessage("Order fulfilled: " + data.order_id);
      var orderElement = document.querySelector(`[data-order-id="${data.order_id}"]`);
      if (orderElement) {
        orderElement.remove();
        document.getElementById("order-count").innerText = state.customer_orders.length;
      }
    });

    document.getElementById("oven-on").addEventListener("click", function() {
      socket.emit('toggle_oven', { state: "on" });
    });
    document.getElementById("oven-off").addEventListener("click", function() {
      socket.emit('toggle_oven', { state: "off" });
    });
    document.getElementById("start-round").addEventListener("click", function() {
      socket.emit('start_round', {});
    });
    window.addEventListener("beforeunload", function () {
      socket.disconnect();
    });

    socket.on('game_state_update', function(update) {
      if (update.customer_orders) state.customer_orders = update.customer_orders;
      if (update.pending_orders) state.pending_orders = update.pending_orders;
      updateGameState(state);
    });

    socket.on('room_expired', function(data) {
      updateMessage(data.message);
      var roomModal = new bootstrap.Modal(document.getElementById('roomModal'), {
        backdrop: 'static',
        keyboard: false
      });
      roomModal.show();
      socket.emit('request_room_list');
    });


let leadTimeChart;

function prepareChartData(leadTimes) {
    // Sort by actual build start time, ascending
    leadTimes.sort((a, b) => a.start_time - b.start_time);

    const labels = leadTimes.map((lt, index) => `Pizza ${index + 1}`);
    const completedData = leadTimes.map(lt => lt.status === "completed" ? lt.lead_time : null);
    const incompleteData = leadTimes.map(lt => lt.status === "incomplete" ? lt.lead_time : null);

    renderLeadTimeChart(labels, completedData, incompleteData);
}


function renderLeadTimeChart(labels, completedData, incompleteData) {
    const ctx = document.getElementById('leadTimeChart').getContext('2d');

    // Destroy existing chart if it exists
    if (leadTimeChart) {
        leadTimeChart.destroy();
    }

    // Create new chart with two datasets
    leadTimeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Completed Pizzas',
                    data: completedData,
                    borderColor: 'rgba(75, 192, 75, 1)', // Green for completed
                    backgroundColor: 'rgba(75, 192, 75, 0.2)',
                    pointBackgroundColor: 'rgba(75, 192, 75, 1)',
                    pointBorderColor: 'rgba(75, 192, 75, 1)',
                    fill: false,
                    spanGaps: true // Connects points even with null values
                },
                {
                    label: 'Incomplete Pizzas',
                    data: incompleteData,
                    borderColor: 'rgba(255, 99, 132, 1)', // Red for incomplete
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    pointBackgroundColor: 'rgba(255, 99, 132, 1)',
                    pointBorderColor: 'rgba(255, 99, 132, 1)',
                    fill: false,
                    spanGaps: true
                }
            ]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Lead Time (Seconds)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Pizza Sequence'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Lead Times for All Pizzas'
                },
                legend: {
                    display: true // Show legend to distinguish completed vs incomplete
                }
            }
        }
    });
}
