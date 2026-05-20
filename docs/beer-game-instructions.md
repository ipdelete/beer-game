# Instructions for Running the Production-Distribution Game
## "The Beer Game"

*Adapted from Instructions written by John Sterman*  
*Revised by System Dynamics Society, May 1998*

**System Dynamics Society**  
Milne 300 - Rockefeller College  
University at Albany - State University of New York  
Albany, NY 12222  
Phone: (518) 442-3865 | Fax: (518) 442-3398  
E-mail: System.Dynamics@albany.edu  
Website: http://www.albany.edu/cpr/sds/

---

This document outlines the protocol for the Production-Distribution Game (The Beer Game), developed to introduce people to concepts of system dynamics. The game can be played by as few as four and as many as 60 people (assistance is required for larger groups). The only prerequisite, besides basic math skills, is that none of the participants have played the game before, or else agree not to reveal the "trick" of the game.

## 1. Purpose

- **a.** Introduce people to the key principle "structure produces behavior"
- **b.** Experience the pressures of playing a role in a complex system

## 2. Overview of Production-Distribution System

- **a.** Identify the four positions on the board: retailer, wholesaler, distributor, and factory. Each board will have one or two players at each position. Each board comprises one team.

- **b.** Each position is identical (except for the factory). Each position has an inventory of beer. Each position receives orders from and ships beer to the sector downstream. Each position orders beer from the sector upstream. Beer is received after a shipping delay. (In the case of the factory, beer is received after a production delay.) Orders are received after a mailing delay (orders placed to incoming orders).

## 3. Basic Rules

- **a.** Have each team pick a name for their brewery (e.g. the name of a real beer).* Distribute one Record Sheet to each position and have them label their Record Sheet with the name of their brewery and their position, e.g. retailer, wholesaler, etc.

- **b.** Have each person ante up $1.00, or an appropriate amount, which will go to the winning team, winner takes all.

- **c.** The object of the game is to minimize total costs for your team. The team with the lowest total costs wins. Costs are computed in the following way: The carrying costs of inventory are **$0.50 per case per week**. Out-of-stock costs, or backlog costs, are **$1.00 per case per week**. The costs of each stage (retailer, wholesaler, distributor, factory) for each week, added up for the total length of the game, determine the total cost.

- **d.** **No communication between positions.** Retailers should not talk to anyone else, same for wholesalers, distributors, and factories. The reason for this is that in real life there may be five factories, several dozen distributors, thousands of wholesalers, and tens of thousands of retailers, and each one cannot find out what the total activity of all the others is. The only communication between sectors should be through the passing of orders and the receiving of beer.

- **e.** Retailers are the only ones who know what the customers actually order. They should not reveal this information to anyone else.

> **Note:** The product represented by the chips does not have to be beer. Any product appropriate to the group may be chosen by the facilitators.

## 4. Steps of the Game

The game leader should call out the steps as the game progresses. The first few times when the system is still in equilibrium the leader should go through the steps very slowly to make sure people have the mechanics down. Notice that of the five steps of the game, only the last, placing orders, involves a decision. The first four steps only involve moving inventory of beer or order slips, and are purely mechanical. For the first few weeks the leader should tell everyone to order four units to keep the system in equilibrium.

### Game Steps:

1. **Receive inventory and advance the shipping delays.**
   - Factory advance the production delay.

2. **Look at incoming orders and fill orders.** (Retailer looks at customer order cards. Factory looks at incoming orders, not the production request.)
   - All incoming orders plus orders in backlog must be filled.
   - If your inventory is insufficient to fill incoming orders plus backlog, fill as many orders as you can and add the remaining orders to your backlog.

3. **Record your inventory or backlog.**

4. **Advance the order slips; and the brewery brews.** That is, the factory converts the production request from last week into cases of beer and put the cases (chips) in the first production delay.

5. **Place and record your orders.** Factory places and records its production requests.

## 5. Initialization of the Boards

- **a.** There should be twelve chips (or coins) representing twelve cases of beer in each inventory. Each chip or coin represents one case. There should be four chips in each shipping box and production delay. There should be order slips with "4" written on them, face down in each order box (orders placed, incoming orders, and production requests). A supply of blank order slips should be available at each position. A supply of chips should be placed at the factory for production of new cases of beer.

- **b.** Place the customer order cards in the "order cards" box, with the order numbers face down, and the week number showing. Weeks 1 through 50 should be in order. The customer order cards with the customer demand should not be revealed in advance. The pattern of customer demand that is most effective for first-time players is a pattern of **four cases per week until week five, and then eight per week from week five on**. Each order deck should have fifty weeks' worth of cards, and the players should be told that the game will be fifty weeks long. Typically it is only necessary to run the game thirty-five weeks or so in order to see the pattern of fluctuation, but telling the players it will be fifty weeks prevents horizon effects, where they run their inventories down because they feel the end of the game is coming.

## 6. Tips

- **a.** It is very helpful if the game leader makes sure that each team stays in step so that he/she can quickly glance around the room and see that everyone is at the right place.

- **b.** The game leader should write the current week on the blackboard or flip chart as the steps for that week are called out.

- **c.** In about the eighth or ninth week the retailer will run out of inventory and have a backlog for the first time. People do not understand the meaning of backlogs, or the cumulative nature of the backlog. It is necessary to stop the game at this point, ask everyone to pay attention, and explain how backlog accounting works. Explain that the backlog represents orders you have received, but have not yet filled, and which you must fill in the future. Explain that the backlog is cumulative. "Next week you have to fill the incoming orders that you receive, plus whatever is in your backlog, if possible. If not possible, then the amount left over is added to the existing backlog and must be filled in later weeks." Emphasize at this point that **backlog costs twice as much as inventory**. You may need to do this one or two more times, and should be careful to check and be sure that they do in fact fill their backlog. It is helpful to write the following equation on the blackboard to help with backlog accounting:

   ```
   Orders to fill   =   New orders   +   Backlog
   this week            this week        last week
   ```

- **d.** The game can be played in as little as one and a half hours if the leader maintains a very brisk pace. The debriefing usually requires at least 40 minutes and can be expanded substantially.

## 7. End of Game

- **a.** Halt the game after about 36 weeks (but play the game up to that point as if it is going on to 50 weeks, to avoid unusual end-of-game moves).

- **b.** Ask each position on each team to calculate their total cost:
   ```
   Cost = Total Inventory × $0.50 + Total Backlog × $1
   ```
   and to mark the total cost on the Record Sheet for the position.

- **c.** Pass out Orders graph sheets - one to each position. Ask each position to graph their own orders, week by week. Clarify to Factory that they will graph their Production Requests.

- **d.** Pass out Effective Inventory graph sheets - one to each position. Ask each position to graph the inventory week by week, showing any backlog as negative inventory.

- **e.** Team name and position must be indicated on all sheets. Once the graph is complete, have the players connect the dots with a bold magic marker (color coded - black, blue, green and red - to the board) for ease of viewing by the group.

- **f.** Pass out the Customer Order graph sheets to everyone except Retailers. Ask each person to sketch what he or she thinks the customer order rate looked like over time. Ask each to indicate a simple scale or maximum value.

   **Ask Retailers not to discuss anything about customer orders until after the debrief of the game.**

- **g.** Collect all the sheets, and send players off for a break.

- **h.** During break:
   - a) Calculate team costs to determine the winner, and compute the average team cost.
   - b) Tape sheets together and hang up team graphs.

### Graph Layout:
```
Effective Inventory               Orders/Production Requests

    Retailer                            Retailer
    Wholesaler                          Wholesaler
    Distributor                         Distributor
    Factory                             Factory
```

---

## Tolstoy on the "Laws of History"
*War and Peace, Part 11, I:*

"The first fifteen years of the nineteenth century present the spectacle of an extraordinary movement of millions of men. Men leave their habitual pursuits; rush from one side of Europe to the other; plunder, slaughter one another, triumph and despair; and the whole current of life is transformed and presents a quickened activity, first moving at a growing speed, and then slowly slackening again. What was the cause of that activity, or from what laws did it arise? asked the human intellect.

The historians, in reply to that inquiry, lay before us the sayings and doings or some dozens of men in one of the buildings of the city of Paris, summing up those doings and sayings by one word--revolution. Then they give us a detailed biography of Napoleon, and of certain persons favorably or hostilely disposed to him; talk of the influence of some of these persons upon others; and then say that this it is to which that activity is due, and these are its laws.

But the human intellect not only refuses to believe in that explanation, but flatly declares that the method of explanation is not a correct one, because in this explanation a smaller phenomenon is taken as the cause of a greater phenomenon. The sum of men's individual wills produced both the revolution and Napoleon; and only the sum of those wills endured them and then destroyed them.

'But whenever there have been wars, there have been great military leaders; whenever there have been revolutions in states, there have been great men,' says history. 'Whenever there have been great military leaders there have, indeed, been wars,' replies the human reason; 'but that does not prove that the generals were the cause of the wars, and that the factors leading to warfare can be found in the personal activity of one man.'

...

For the investigation of the laws of history, we must completely change the subject of observations, must let kings and ministers and generals alone, and study the homogeneous, infinitesimal elements by which masses are led. No one can say how far it has been given to man to advance in that direction in understanding of the laws of history. But it is obvious that only in that direction lies any possibility of discovering historical laws; and that the human intellect has hitherto not devoted to that method of research one millionth part of the energy that historians have put into the description of the doings of various kings, ministers, and generals...."

---

## Outline for Post-Game Discussion

1. Get all the graph sheets of results (Orders, Effective Inventory) taped up for display.

2. Find out which team won (lowest total cost) and distribute the winnings.

3. Although they played the game to minimize cost, that is not the real purpose of the game.

### The game is designed to:
1) Give them an experience of playing a role in a system
2) Show them how "structure produces behavior"

4. Ask participants what their experience of playing the game was. Some good leading questions are:
   - Did you feel yourself "at the mercy" of forces in the system from time to time? Did you feel the effects of the forces in the system from time to time? (i.e., relatively helpless in the face of huge incoming orders or excess inventories)
   - Did you find yourself "blaming" the person next to you for your problems?

5. After a few minutes (about 10) of discussion, look at the graphs of the results. Ask them, "What commonalities do you see in the graphs for the different teams?" Participants should see common pattern of overshoot and oscillation. This should be most evident in the effective inventory graph.

   - Get them to really see for themselves that different people in the same structure produce qualitatively similar results. Even though they acted very differently as individuals in ordering inventory, still the overall patterns of behavior are similar.
   
   - Differences in individual ordering patterns (free will) result in the quantitative differences in game results. But the qualitative patterns are the same.
   
   - **This is a very important point--take as long as necessary to have them see it for themselves.**
   
   You might reflect at this point on what happens in the real world when such order-rate and inventory oscillations are generated. The typical organizational response is to find the "person responsible" (the guy placing the orders or the inventory manager) and blame him. The game clearly demonstrates how inappropriate this response is--different people following different decision rules for ordering all generated oscillations.

6. After having had them all see the extent to which different people produce similar results in a common structure, you then need to move on to what is usually the most powerful point made by the game: that **internal structure, not external events, cause system behavior**. The way to make this point is to ask the following question:

   "All of you who were not retailers, or who otherwise have not found out what the pattern of customer orders was, what do you think the customers were doing?"

   Most people usually believe that customer demand was fluctuating because they believe that the system fluctuations must have been externally driven. Get each of them (other than retailers) to see that they assumed fluctuating customer orders.

   - Show the Customer Order charts that were filled out at the end of the game (Sketch a few on an single overhead transparency. Then go to one team's graphs and carefully draw in the customer order rate on the Factory's Order (Production Requests) graph. The small step from from 4 to 8 orders should make a strong visual impression in contrast to the order rate fluctuations which often have an amplitude of 20 to 40 orders per week. Moreover, the sustained oscillations generated by the system contrast sharply to the absolutely flat customer order rate after the step at week 5.

   This simple exercise of getting them to see how, contrary to their expectations, the internal system structure is completely capable of generating fluctuating behavior is the most profound lesson they can learn from the game.

   - **It is important that they see this for themselves, as a demonstration or an experimental result which they did, not as an idea of which you are trying to convince them.** In fact, the game is an experiment in very true sense. The result of oscillating behavior was not predetermined.

7. The assumption that the system's problems are caused by the customer stems from the external orientation most of us adopt in dealing with most problems. In a sense, this is just an extension of the viewpoint that attributes your problems to the person(s) playing next to you in the game: "he/she did it to me" is a special case of "they (the customers) did it to me". In system dynamics we take an alternative viewpoint--that the internal structure of a system is more important than external events in generating qualitative patterns of behavior. This can be illustrated by this diagram:

   ```
                                   events
                       (such as inventory stock-outs
                         and extreme order surges)

                      behavior/process (oscillation)

                               structure
   ```

   Most people try to explain reality by showing how one set of events causes another or, if they have studied a problem in more depth, by showing how a particular set of events are part of a longer-term historical process.

   - Have the participants illustrate this for themselves by looking at their own "explanations" for events during the game. Take a particular incident in the game, for example a large surge in production requests at the factory, and ask the people responsible why they did that. Their answer will invariably relate their decision to some prior decision of the people they supply or who supply them. Then turn to those people and ask them why they did that. Continue this until people see that one can continue to relate one event to earlier events indefinitely.

   The basic problem with the "events cause events" orientation is that it gives you very little power to alter the course of events. The focus on internal structure greatly enhances the possibilities of influencing the course of events because you are dealing with the underlying source of the process, not just trying to manipulate events.

   > The slinky demonstration on the training video is a good way to emphasize the focus on internal structure -- the slinky oscillates not just because the hand was withdrawn but mainly because there is something about the structure of a spring that wants to oscillate. (Please note: This training video is currently in production and not yet available.)

8. If time permits, have students think of examples of problems which can be viewed as internally or externally caused.
   
   Examples: illness, famine

9. This leaves you at the point of dealing with the problem:

   "How do we deal more effectively with underlying structure?"

   - This is the purpose of system dynamics. So you are in an excellent position to begin introducing system dynamics tools for understanding underlying structure.

---

## Game Materials Checklist

### Per Team (or board)
- [ ] Game board (1)
- [ ] Single chips (500-600)
- [ ] Ten chips (30) (optional, can replace some single chips)
- [ ] Customer order cards (1)
- [ ] Order slips (200)
- [ ] Graphs:
  - Effective Inventory (4)
  - Orders (4)
  - Customer Orders (3)
- [ ] Record sheets (4)
- [ ] Pencils (4)
- [ ] Markers in four colors (1 each):
  - Green
  - Blue
  - Red
  - Black
- [ ] Calculators (2)

### Per Session
- [ ] Masking tape
- [ ] Outline for post-game discussion
- [ ] Orders to Fill sheet
- [ ] Flip charts (optional)
- [ ] Slinky (optional)
- [ ] Previous game graphs (if available)

### What you receive with one complete set:
- Game board (1)
- Video (1)
- Customer order cards (1)
- Single chips (600)
- Printed instructions including record sheet, graphs, etc. to be duplicated
- Articles relating to the Beer Game

### What you need to purchase/obtain:
- Markers in four colors
- Masking tape
- Pencils
- Flip chart (if needed)
- Calculators
- Slinky (optional)

### What you need to duplicate/make for distribution:

**Graphs (Copy):**
1. Record Sheet (4 per team) - One per position
2. Effective Inventory graph (4 per team) - One per position
3. Orders graph (4 per team) - One per position
4. Customer Orders graph (3 per team) - One for wholesaler, distributor and factory only, not retailer

**Blank Order Slips:**
- 50 placed at each position
- You may use small "Post-it" notes, or cut paper into small rectangles measuring approximately 1.5" x 2"
- Make seven order slips per game board with "4" on each one, and place them face down in each of the "orders" boxes to initialize the game board

> **Note:** Order slips showing "4" are placed face down on the game board. Customer order cards are placed in "Customer Orders" box.

---

## Orders to Fill Formula

### 1. Orders to fill = Backlog + Current Orders

### 2a. If you have enough inventory:
Ship all the orders to ship and record your new inventory.

### 2b. If you do not have enough inventory:
Ship all the inventory you have and record the remaining unfilled orders to fill as your new backlog.

---

## The Beer Distribution Game: An Annotated Bibliography
*Covering its History and Use in Education and Research*

**Prepared by John D. Sterman**  
Sloan School of Management  
Massachusetts Institute of Technology  
Cambridge, MA 02139  
(617) 253-1951 (voice); (617) 253-6466 (fax); jsterman@mit.edu (email)

*April 1992; revised July 1992*

The Beer Distribution Game dates to the earliest days of system dynamics. The game has been used for three decades as an introduction to systems thinking, dynamics, computer simulation, and management. It has been played by thousands of people, all over the world, from high-school students to CEOs of major corporations. The references below provide useful information for those who want to follow up the experience of the game. These works describe the history of the game, the equations for simulating the game on a computer, the success of organizational change efforts based on the original model embodied in the game, the psychological processes people use when playing, and even how these processes can produce chaos.

### Key References

**Forrester, J.W. (1958)** Industrial Dynamics: A Major Breakthrough for Decision Makers. *Harvard Business Review*, 36(4), July/August, 37-66.
> The first article in the field of system dynamics. Presents the production-distribution system as an example of dynamic analysis of a business problem. Reprinted in Roberts (1978).

**Forrester, J.W. (1961)** *Industrial Dynamics*. Cambridge MA: Productivity Press.
> Contains the material in Forrester 1958 expanded to include additional discussion of policies to improve performance in the production-distribution system. Also includes complete equations for a computer model of the system from which the Beer Game was derived. Describes the results of many policy experiments. Industrial Dynamics is the classic work in the field and remains an extremely useful reference and text thirty years after publication.

**Jarmain, W. E. (ed.) (1963)** *Problems in Industrial Dynamics*. Cambridge, MA: MIT Press.
> Contains a description of an early version of the Beer Distribution Game

**MacNeil-Lehrer Report (1989)** Risky Business - Business Cycles, Video, Public Broadcasting System, aired 23 October 1989.
> Videotape showing students in John Sterman's Systems Dynamics course at MIT playing and discussing the Beer Game. Relates the game to boom and bust cycles in the real world. Excellent in debriefing the game, and helpful to those seeking to learn how to run the game. Copies available from System Dynamics Group, E60-388, MIT, Cambridge MA 02139.

**Mosekilde, E., E. R. Larsen & J. D. Sterman (1991)** Coping with complexity: Deterministic Chaos in human decision making behavior. In J.L. Casti & A. Karlqvist (Eds.), *Beyond Belief: Randomness, Prediction, and Explanation in Science*, 199-229. Boston: CRC Press
> Shows how simple and reasonable decision rules for playing the Beer Game may produce strange nonlinear phenomena, including deterministic chaos.

**Radzicki, M. (1991)** Computer-based beer game boards. Worcester Polytechnic Institute, Dept. of Soc Sci and Policy Studies, Worcester, MA 01609-2280
> Beer game boards in PICT format for Macintosh computers available on disk for $5.00; all proceeds go to the System Dynamics Society.

**Thomsen, J.S., E. Mosekilde, & J.D. Sterman (1992)** Hyperchaotic Phenomena in Dynamic Decision Making. *Systems Analysis and Modelling Simulation*, forthcoming.
> Extends earlier papers by Moskilde, Sterman, et al. to examine hyperchaotic modes in which the behavior of the beer distribution system may switch chaotically among several different chaotic attractors (for aficionados, "hyperchaos" exists when a dynamical system contains multiple positive Lyapunov exponents).

**Roberts, E.B., ed. (1978)** *Managerial Applications of System Dynamics*. Cambridge, MA: Productivity Press.
> Excellent anthology of early applied system dynamics work in organizations, including analysis of efforts to implement the results of the model which led to the Beer Game.

**Roberts, E.B. (1978)** Equations for the Production-Distribution System, in Roberts, E.B.(ed.) *Managerial Applications of System Dynamics*. Cambridge, MA: Productivity Press.
> Presents documented equation listing for the production-distribution system based on Forrester (1961), in the DYNAMO computer simulation language.

**Senge, P. (1990)** *The Fifth Discipline*. New York: Doubleday.
> Excellent non-technical discussion of the Beer Game, and systems thinking principles generally.

**Sterman, J.D. (1984)** Instructions for Running the Beer Distribution Game. D-3679, System Dynamics Group, MIT, E60-388, Cambridge, MA 02139.
> Explains how to run and debrief the Beer Game, including layout of boards, set up, play, and discussion. Incorporates debriefing notes by Peter Senge. Some people have found this document, in conjunction with the MacNeil/Lehrer video and plenty of practice, is sufficient to enable them to lead the game successfully.

**Sterman, J.D. (1988)** Deterministic Chaos in Models of Human Behavior: Methodological Issues and Experimental Results. *System Dynamics Review*, 4, 148-178.
> The decision rules people use when playing the Beer game can lead to deterministic chaos.

**Sterman, J.D. (1989)** Modeling Managerial Behavior: Misperceptions of Feedback in a Dynamic Decision Making Experiment. *Management Science*, 35(3), 321-339.
> Detailed analysis of Beer Game results. Examines why people do so poorly in the Beer Game. Proposes and tests a model of the decision making processes people use when playing the game and shows why they do so badly.

Additional information on systems dynamics, including publications, simulation games, management flight simulators, journals, etc. is available from John Sterman at the address above.

---

*If you know of additional publications which discuss aspects of the game not included in this bibliography please send a copy to John Sterman at the address above so they can be incorporated in future revisions.*