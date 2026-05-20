# Beer Game Player Cheat Sheet

## Objective

**Minimize your team's total costs** across all 4 positions (Retailer → Wholesaler → Distributor → Factory)

## Cost Structure ⚠️

- **Inventory holding**: $0.50 per case per week
- **Backlog (unfilled orders)**: $1.00 per case per week
- **Backlog costs TWICE as much as inventory!**

## Critical Rules

- ❌ **NO COMMUNICATION** between positions
- ❌ **NO SHARING** of information about orders or inventory
- ✅ Only communicate through order slips and beer shipments
- 🕒 Game runs for 50 weeks (but may end earlier)

## The 5 Game Steps (Every Week)

### 1. Receive Inventory

- Move beer from shipping delay to your inventory
- **Factory**: Move beer from production delay

### 2. Fill Orders

- **Formula**: Orders to fill = New incoming orders + Backlog from last week
- Fill as many as possible from inventory
- Any unfilled orders become backlog (carry forward to next week)

### 3. Record

- Write current inventory OR backlog on your record sheet
- Calculate weekly cost: `(Inventory × $0.50) + (Backlog × $1.00)`

### 4. Advance Slips

- Move order slips through the delay pipeline
- **Factory**: Move production requests through production delay

### 5. Place Orders (DECISION POINT!)

- **Retailer**: Order from Wholesaler
- **Wholesaler**: Order from Distributor  
- **Distributor**: Order from Factory
- **Factory**: Set production level (no upstream supplier)

## Key Formulas

### Orders to Fill

```text
Orders to fill = New orders + Backlog from last week
```

### Weekly Cost

```text
Weekly Cost = (Inventory × $0.50) + (Backlog × $1.00)
```

### Total Game Cost

```text
Total Cost = Sum of all weekly costs
```

## Position-Specific Notes

### Retailer

- ✅ You see actual customer orders (KEEP SECRET!)
- ❌ Don't reveal customer demand to anyone
- 📝 Order from Wholesaler based on customer needs + inventory management

### Wholesaler

- 📝 You only see Retailer orders (delayed by 2 weeks)
- 🤔 You don't know actual customer demand
- 📝 Order from Distributor based on Retailer orders + inventory management

### Distributor  

- 📝 You only see Wholesaler orders (delayed by 2 weeks)
- 🤔 You don't know actual customer demand
- 📝 Order from Factory based on Wholesaler orders + inventory management

### Factory

- 📝 You only see Distributor orders (delayed by 2 weeks)
- 🤔 You don't know actual customer demand
- 🏭 Set production levels (takes 2 weeks to complete)
- ♾️ Unlimited production capacity

## Strategy Tips

### Think About

- Your current inventory level
- Your current backlog
- Incoming orders you need to fill
- Orders in the pipeline (delays)
- Recent trends in demand

### Common Mistakes

- 🚫 Over-ordering when you see big incoming orders
- 🚫 Under-ordering when inventory gets low
- 🚫 Forgetting about orders in the delay pipeline
- 🚫 Not accounting for backlog growth

## Delays to Remember

- **Shipping delays**: 2 weeks for beer to arrive
- **Order delays**: 2 weeks for your orders to reach supplier
- **Production delays** (Factory only): 2 weeks for production to complete

## Record Keeping

Track each week:

- Starting inventory
- Orders received  
- Orders filled
- Ending inventory/backlog
- Order placed upstream
- Weekly cost

**Winner**: Team with lowest total cost across all positions!
