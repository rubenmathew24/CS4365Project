"""
PacMan CTF AI
CS 4365 Final Project
By Ruben & Daniel
"""

from captureAgents import CaptureAgent
import random, time, util
from game import Directions
import game
from distanceCalculator import Distancer
from util import nearestPoint, manhattanDistance, PriorityQueueWithFunction
import math
#import sys

BIG_NUMBER = 10000

#################
# Team creation #
#################

# For Referecnce:
# If Red: firstIndex = Red Agent, secondIndex = Orange Agent
# If Blue: firstIndex = Blue Agent, secondIndex = Teal Agent

def createTeam(firstIndex, secondIndex, isRed,
               first = 'DefensiveAgent', second = 'OffensiveAgent'):

  return [eval(first)(firstIndex), eval(second)(secondIndex)]

##########
# Agents #
##########

class DummyAgent(CaptureAgent):

  def registerInitialState(self, gameState):

    # Built-in register, provides real distancer
    CaptureAgent.registerInitialState(self, gameState)

    # Determine team/side
    self.redTeam = gameState.isOnRedTeam(self.index)
    
    # Indices of each agent
    self.teamIndices = gameState.getRedTeamIndices()
    self.enemyIndices = gameState.getBlueTeamIndices()
    if not self.redTeam:
      self.teamIndices = gameState.getBlueTeamIndices()
      self.enemyIndices = gameState.getRedTeamIndices()

    # Important positions
    self.startPos = gameState.getAgentPosition(self.index)
    walls = gameState.getWalls()
    self.middleWidth = walls.width / 2    # True middle
    self.middleHeight = walls.height / 2  # True middle
    self.mapWidth = walls.width

    # Find borders
    self.teamBorder = math.floor(self.middleWidth) - 1
    self.enemyBorder = math.floor(self.middleWidth)
    if not gameState.isOnRedTeam(self.index):
      self.teamBorder = math.floor(self.middleWidth)
      self.enemyBorder = math.floor(self.middleWidth) - 1
    
    # Find exit tiles, sorted by distance from center
    if not hasattr(self, 'exits'):
      self.gaps = [] 
      # Determine if each border tile is exit (both sides open)
      for y in range(walls.height):
        if not walls[self.teamBorder][y] and not walls[self.enemyBorder][y]:
          self.gaps.append((self.teamBorder, y))
      
  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)

    # Evaluate each action for h value
    #self.debugClear()
    start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    #print('eval time for agent %d: %.4f' % (self.index, time.time() - start))

    # Find actions of max value
    bestValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    #print(type(self), "Best Actions:", bestActions, "Best Value:", bestValue)
    #print(list(zip(actions,values)))
    return random.choice(bestActions)   # Return random best action
  
  def evaluate(self, gameState, action):
    # Determines value based on features and their weights
    features = self.getFeatures(gameState, action)
    weights = self.getWeights(gameState, action)
    #print("\n","\t"+action + ": " + str(features * weights), "F: " + str(features), "W: " + str(weights), "\n", sep="\n\t")
    return features * weights
  
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor

  def getDisToOffensiveEnemy(self, gameState, succPos):
    minDis = BIG_NUMBER
    for enemy in self.enemyIndices:
      enemyPos = gameState.getAgentPosition(enemy)
      if self.onTeamSide(enemyPos):
        disToEnemy = self.getMazeDistance(succPos, enemyPos)
        if disToEnemy < minDis:
          minDis = disToEnemy
    return minDis
    
  # Returns list of gaps sorted by proximity
  def findClosestGaps(self, pos):
    gapDistances = []
    for gap in self.gaps:
      gapDistances.append(self.getMazeDistance(gap, pos))
    gapsByDis = sorted(zip(self.gaps, gapDistances), key=lambda pair : (pair[1], abs(self.middleHeight - pair[0][1])))
    return gapsByDis
  
  def adjacentEnemies(self, pos):
    up = (pos[0], pos[1]+1)
    down = (pos[0], pos[1]-1)
    left = (pos[0]-1, pos[1])
    right = (pos[0]+1, pos[1])
    return (up == self.enemy1['pos'] or down == self.enemy1['pos'] or left == self.enemy1['pos'] or right == self.enemy1['pos'] or
            up == self.enemy2['pos'] or down == self.enemy2['pos'] or left == self.enemy2['pos'] or right == self.enemy2['pos'])

  def enemyWithMostFood(self):
    if (self.enemy1['numCarrying'] == 0 and self.enemy2['numCarrying'] == 0):
      return None
    if (self.enemy1['numCarrying'] > self.enemy2['numCarrying']):
      return self.enemy1
    else:
      return self.enemy2
  # Determines if agent is on our team's side
  def onTeamSide(self, pos):
    if self.redTeam: 
      return pos[0] in range(math.floor(self.middleWidth))
    else:
      return pos[0] in range(math.floor(self.middleWidth), self.mapWidth)

class OffensiveAgent(DummyAgent):

  def registerInitialState(self, gameState):
    DummyAgent.registerInitialState(self, gameState)

    self.history = []
    self.totalFood = len(self.getFood(gameState).asList())
    self.originalCapsules = self.getCapsules(gameState)
    self.risky = self.findRiskyPositions(gameState)

    # Save the default weights because weights can be changed
    self.defaults = {'eatFood': 100, # Prioritize eating food
                    'eatCapsule': 2000, # Prioritize eating capsules
                    'distanceToCapsule': -40,  # Prioritize getting close to capsules
                    'distanceToFood': -15,  # Prioritize getting close to food
                    'distanceToExit': -1,  # Prioritize getting close to exit
                    'distanceFromEnemy' : 10, # Prioritize getting far from enemy
                    'neverStop' : -1, # Be a shark, never stop moving
                    'onOurSide' : -40000000, # Discourage staying on our side
                    'risky': -100, # Discourage going to risky positions
                    'improveScore': 1000000, # Prioritize improving score
                    'quickGetaway' : 100 # If can quickly deposit food, do it
                    }

    # Weights that will be returned
    self.weights = self.defaults.copy()

    # Set up Defensive capabilities
    # Enemy Info
    enemy1Index = self.enemyIndices[0]
    self.enemy1 = {}
    self.enemy1['index'] = enemy1Index
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['startPos'] = gameState.getInitialAgentPosition(self.enemy1['index'])
    self.enemy1['movesSpentAttacking'] = 0
    self.enemy1['vulnerableTurns'] = 0

    enemy2Index = self.enemyIndices[1]
    self.enemy2 = {}
    self.enemy2['index'] = enemy2Index
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['startPos'] = gameState.getInitialAgentPosition(self.enemy2['index'])
    self.enemy2['movesSpentAttacking'] = 0
    self.enemy2['vulnerableTurns'] = 0

    # Construct heat map
    self.map = [ [0]*gameState.getWalls().width for i in range(gameState.getWalls().height)]

  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)
    myPos = gameState.getAgentPosition(self.index)
    # Evaluate each action for h value
    #start = time.time()
    #self.debugClear()
    values = [self.evaluate(gameState, a) for a in actions]
    #print('eval time for agent %d: %.4f' % (self.index, time.time() - start))

    # Collect enemy info
    enemy1Gaps = self.findClosestGaps(self.enemy1['pos'])
    self.enemy1['gapMain'] = enemy1Gaps[0]
    self.enemy1['gapAlt'] = enemy1Gaps[1]
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['onTeamSide'] = self.onTeamSide(self.enemy1['pos'])
    self.enemy1['numCarrying'] = gameState.getAgentState(self.enemy1['index']).numCarrying
    self.enemy1['vulnerableTurns'] = self.enemy1['vulnerableTurns'] - 1 if self.enemy1['vulnerableTurns'] > 0 else 0
    enemy2Gaps = self.findClosestGaps(self.enemy2['pos'])
    self.enemy2['gapMain'] = enemy2Gaps[0]
    self.enemy2['gapAlt'] = enemy2Gaps[1]
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['onTeamSide'] = self.onTeamSide(self.enemy2['pos'])
    self.enemy2['numCarrying'] = gameState.getAgentState(self.enemy2['index']).numCarrying
    self.enemy2['vulnerableTurns'] = self.enemy2['vulnerableTurns'] - 1 if self.enemy2['vulnerableTurns'] > 0 else 0

    # Determine heat
    for i in range(len(self.map)):
      for j in range(len(self.map[i])):
        if self.map[i][j] > 0:
          self.map[i][j] -= .5
    self.map[myPos[1]][myPos[0]] += 1

    # Find actions of max value
    bestValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    #print(type(self), "Best Actions:", bestActions, "Best Value:", bestValue)
    #print(list(zip(actions,values)))

    move = random.choice(bestActions)

    # ANTI GRIDDY (Stop going back and forth between two actions)
    if len(self.history) > 5:
      temp = self.history[-5:]
      if temp[0] == temp[2] == temp[4] and temp[1] == temp[3] == move and temp[0] != temp[1]:
        # print("NO MORE GRIDDY")
        allActions = sorted(zip(actions, values), key=lambda x: x[1], reverse=True)
        for a in allActions:
          if a[0] != move:
            move = a[0]
            break
        # print("NEW MOVE:", move)
        # exit(0)
        
    #DEBUG RISKY
    # for risk in self.risky:
    #   # if gameState.getAgentState(self.index).getPosition() == risk and not self.onTeamSide(risk): exit(0)
    #   self.debugDraw(risk, [.2,.3,0], clear=False)

    self.history.append(move)
    return move # Return random best action

  def getFeatures(self, gameState, action):
    successor = self.getSuccessor(gameState, action)
    myPos = successor.getAgentState(self.index).getPosition()

    # If we are on our side and in a winning state, play defensively
    if self.onTeamSide(myPos) and self.getScore(successor) > 5:
      return self.getDefensiveFeatures(gameState, action)
    else:
      return self.getOffensiveFeatures(gameState, action)

  def getWeights(self, gameState, action):
    successor = self.getSuccessor(gameState, action)
    myPos = successor.getAgentState(self.index).getPosition()

    # If we are on our side and in a winning state, play defensively
    if self.onTeamSide(myPos) and self.getScore(successor) > 5:
      return self.getDefensiveWeights(gameState, action)
    else:
      return self.getOffensiveWeights(gameState, action)

# Offensive mode:

  def getOffensiveFeatures(self, gameState, action):
    features = util.Counter()
    successor = self.getSuccessor(gameState, action)
    foodList = self.getFood(successor).asList()  
    capsuleList = self.getCapsules(successor)
    enemyList = self.getOpponents(successor)
    myPos = successor.getAgentState(self.index).getPosition()
    numCarrying = gameState.getAgentState(self.index).numCarrying

    self.resetWeights()

    # Prioritize improving score
    features['score'] = self.getScore(successor)

    # Stops it from stalling
    if action == Directions.STOP: features['neverStop'] += 99999999999

    # Prioritize not being our side unless its an exit
    if self.onTeamSide(myPos) and myPos not in self.gaps:
      features['onOurSide'] = 2
      self.weights['distanceToExit'] = -10
    elif myPos in self.gaps and numCarrying == 0:
      features['onOurSide'] = 1

    # Prioritize eating food
    features['eatFood'] = -len(foodList)

    # Priortize eating capsules
    features['eatCapsule'] = -len(capsuleList)

    # Compute distance to the nearest capsule
    if len(capsuleList) > 0: 
      minDistance = min([self.getMazeDistance(myPos, capsule) for capsule in capsuleList])
      features['distanceToCapsule'] = minDistance

    # Compute distance to the nearest exit
    minDistanceToExit = 1000
    if len(self.gaps) > 0: # This should always be True,  but better safe than sorry
      minDistanceToExit = min([self.getMazeDistance(myPos, exit) for exit in self.gaps])
      features['distanceToExit'] += minDistanceToExit

    # If can make a quick getaway, do it
    currentDistanceFromExit = min([self.getMazeDistance(gameState.getAgentState(self.index).getPosition(), exit) for exit in self.gaps])
    if numCarrying >= 2 and currentDistanceFromExit < 5:
      return self.getQuickGetawayFeatures(minDistanceToExit)
    
    # Checks if new position is risky (only on enemy side)
    if myPos in self.risky and not self.onTeamSide(myPos): features['risky'] = 1 + features['distanceToExit']

    # Compute distance to the nearest food
    if len(foodList) > 0: 

      # Find the distance to the closest food
      minDistance = min([self.getMazeDistance(myPos, food) for food in foodList])
      features['distanceToFood'] = minDistance

      # Find the position of the closest food (for later calculations)
      # TODO - This only assumes one closest food, but there could be multiple (Might change later)
      closestFood = None
      for food in foodList:
        if self.getMazeDistance(myPos, food) == minDistance:
          closestFood = food

      # less food available, more likely to be spread apart, so don't worry as much about distance to food
      self.weights['distanceToFood'] = self.defaults['distanceToFood'] * ((len(foodList) / self.totalFood))
      
      # If we are winning, don't need to try as hard
      if self.getScore(successor) > 0: self.weights['distanceToFood'] = -5

    # Increase weight of distance to exit with the more food we have (if we have more than 7, we should be trying to get out)
    self.weights['distanceToExit'] = (-150 if numCarrying > 7 else -(numCarrying * 2))

    # Compute distance to the nearest enemy
    actualDistanceFromEnemy = 1000
    if len(enemyList) > 0:

      # Get the Manhattan distance AND actual distance because might be close but on other side of wall
      minDistance = min([manhattanDistance(myPos, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
      actualDistanceFromEnemy = min([self.getMazeDistance(myPos, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
      features['distanceFromEnemy'] = actualDistanceFromEnemy

      # If enemy is in same region, start worrying about it
      if minDistance < 3: features['distanceFromEnemy'] = 1000

      # If enemy is close, DO NOT go for risky food
      if actualDistanceFromEnemy <= 7: self.weights['risky'] = -1000

      # If enemy is FAR away, increase food weight, don't worry about anything else
      if actualDistanceFromEnemy > 15: 
        return self.getFarFromEnemyFeatures(action, myPos, foodList, numCarrying, features['distanceToFood'])

      # If enemy is incredibly close, and far from exit, prioritize getting away
      if actualDistanceFromEnemy < 3 and currentDistanceFromExit > 3: self.weights['distanceFromEnemy'] = 300

      # If enemy is incredibly close, and close to exit, prioritize going home
      if actualDistanceFromEnemy <= 3 and currentDistanceFromExit <= 3: 
        self.weights['onOurSide'] = 0
        self.weights['distanceToExit'] = -100000
        return features

      # If enemies are not close to food, priortize it MORE (by caring less about distance to enemy)
      minDistanceEnemyFromFood = min([self.getMazeDistance(closestFood, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
      if minDistanceEnemyFromFood < 10 and actualDistanceFromEnemy > 15 and not self.onTeamSide(myPos):
        features['distanceFromEnemy'] = 1000
        return features
      
      # Don't get KILLED DUMMY (HEAVILY PENALIZE FOR MOVING TOWARDS ENEMY)
      if actualDistanceFromEnemy == 1: 
        self.weights['distanceFromEnemy'] = -99999
        self.weights['distanceToExit'] = -99999999

      # If enemy is close, and we are close to capsule, prioritize eating it
      if actualDistanceFromEnemy < 3 and features['distanceToCapsule'] < actualDistanceFromEnemy:
        self.weights['eatCapsule'] = 99999999

    # If we don't have much food, and close to exit (or not close to enemies), don't get capsules
    if (numCarrying < 2 and minDistanceToExit < 3) or (actualDistanceFromEnemy > 5):
      self.weights['distanceToCapsule'] = -500 
      self.weights['eatCapsule'] = -1000

    # If capsule is active (check if enemies are scared)
    scaredTime = min([(successor.getAgentState(enemy).scaredTimer) for enemy in enemyList])
    if scaredTime > 0:
      # If we're carrying good amount of food, prioritize getting home
      if numCarrying > 4: self.weights['distanceToExit'] = -10000

      # Try not to get other capsules if plenty of time left
      if scaredTime > 15: self.weights['distanceToCapsule'] = 5

      # If timer isn't too low, can start heading towards enemies
      if scaredTime > 15:
        self.weights['distanceFromEnemy'] = -self.defaults['distanceFromEnemy'] * 60
        
        # Really chase enemy if they're close
        if actualDistanceFromEnemy < 2: 
          self.weights['distanceFromEnemy'] = -10000
          features['distanceFromEnemy'] = actualDistanceFromEnemy
      
      # If timer is low, prioritize getting home
      else:
        self.weights['distanceToExit'] = -10000000

    # Reset weights if capsule not active
    else:
      self.weights['distanceToCapsule'] = self.defaults['distanceToCapsule']


    return features

  def getOffensiveWeights(self, gameState, action):
    return self.weights

# Defensive mode:
  def getDefensiveFeatures(self, gameState, action):
    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()
    succTeamSide = self.onTeamSide(succPos)
    succGap = self.findClosestGaps(succPos)[0]

    # Enemy Info
    self.enemy1['distanceTo'] =  self.getMazeDistance(succPos, self.enemy1['pos'])
    self.enemy2['distanceTo'] = self.getMazeDistance(succPos, self.enemy2['pos'])
    mainEnemy = self.assessEnemies(self.enemy1, self.enemy2)
    #self.debugDraw(mainEnemy['pos'], [1,0,0], clear=True)

    # Draw gaps
    # self.debugDraw(self.enemy1['gapMain'][0], [1,0,0])
    # self.debugDraw(self.enemy1['gapAlt'][0], [1,.4,.4])
    # self.debugDraw(self.enemy2['gapMain'][0], [0,1,0])
    # self.debugDraw(self.enemy2['gapAlt'][0], [.6,1,.6])

    ### Features ###
    features = util.Counter()
    features['disFromBorder'] = succGap[1]
    features['onEnemySide'] = not self.onTeamSide(succPos)
    features['mainEnemyRisk'] = self.getMazeDistance(succPos, mainEnemy['gapMain'][0])
    features['mainEnemyAltRisk'] = self.getMazeDistance(succPos, mainEnemy['gapAlt'][0])
    features['mainEnemyRiskBalance'] = abs(features['mainEnemyRisk'] - features['mainEnemyAltRisk'])
    features['disToOffensiveEnemy'] = self.getMazeDistance(succPos, mainEnemy['pos']) if self.onTeamSide(mainEnemy['pos']) and action != Directions.STOP else BIG_NUMBER
    features['dontStopOnEnemySide'] = BIG_NUMBER if (not succTeamSide) and action == Directions.STOP else 0
    features['heat'] = self.map[int(succPos[1])][int(succPos[0])] if succTeamSide else 0
    features['willDie'] = 1 if gameState.getAgentState(self.index).scaredTimer > 0 and self.adjacentEnemies(succPos) else 0
    features['pop'] = 1 if self.getDisToOffensiveEnemy(gameState, succPos) < 1 else 0
    features['defensiveMode'] = 1
    return features

  def getDefensiveWeights(self, gameState, action):
    weights = {}
    weights['disFromBorder'] = -100        # Prefer close to border, if returning prioritze escaping
    weights['onEnemySide'] = -5           # Discourage entering enemy side when unnecesary
    weights['mainEnemyRisk'] = -1         # Move towards mainEnemy's mainGap
    weights['mainEnemyAltRisk'] = -1      # Move towards mainEnemy's altGap
    weights['mainEnemyRiskBalance'] = -1  # Prefer in-between of mainEnemy's 2 gaps
    weights['disToOffensiveEnemy'] = -3   # Chase after nearby enemies
    weights['dontStopOnEnemySide'] = -1   # it aint safe out there
    weights['heat'] = -4                  # Discourage getting stuck
    weights['willDie'] = -BIG_NUMBER      # Fear death
    weights['pop'] = BIG_NUMBER           # If can eat enemy, do it
    weights['defensiveMode'] = 9999999    # Being in defensive mode is a GOOOD THING, PLEASE SCORE

    weights['disToFood'] = -1             # For quickgrabbing
    weights['outOfCapsuleTurns'] = -1     # If out of turns, run
    return weights

# Helper functions:
  def assessEnemies(self, enemy1, enemy2):
    mainEnemy = sorted((enemy1, enemy2), key = lambda enemy : enemy['movesSpentAttacking'])[1]
    # print('Offensive Main enemy:', mainEnemy['index'])
    return mainEnemy

  # Reset weights to default
  def resetWeights(self):
    self.weights = self.defaults.copy()

  # finds all positions that have 2 or more walls around them
  def findRiskyPositions(self, gameState):
    walls = gameState.getWalls()
    myPos = gameState.getAgentState(self.index).getPosition()
    indexes = [str(i).zfill(2) for i in range(walls.width)]

    riskyPositions = []

    # Finds all positions that have 6 or more walls around them
    for x in range(walls.width):
      for y in range(walls.height):
        if walls[x][y]: continue
        surroundingWalls = sum([walls[x+1][y],walls[x-1][y],walls[x][y-1],walls[x][y+1],walls[x+1][y+1],walls[x-1][y-1],walls[x+1][y-1],walls[x-1][y+1]])
        if surroundingWalls >= 6 and ((walls[x+1][y] and walls[x-1][y]) or (walls[x][y-1] and walls[x][y+1])):
          riskyPositions.append((x,y))

    extendedRiskyPositions = []

    # Finds all positions that have 3 walls around them or a corner close to a risky position
    for x in range(walls.width):
      for y in range(walls.height):
        if walls[x][y]: continue
        if (x,y) in riskyPositions: continue

        if sum([walls[x+1][y],walls[x-1][y],walls[x][y-1],walls[x][y+1]]) == 3: extendedRiskyPositions.append((x,y))

        if not ((((x+1,y) in riskyPositions) != ((x-1,y) in riskyPositions)) or (((x,y+1) in riskyPositions) != ((x,y-1) in riskyPositions))): continue
        if ((walls[x+1][y] and walls[x-1][y]) or (walls[x][y-1] and walls[x][y+1])): extendedRiskyPositions.append((x,y))

    riskyPositions = riskyPositions + extendedRiskyPositions

    for capsule in self.originalCapsules:
      if capsule in riskyPositions: riskyPositions.remove(capsule)

    # #DEBUG
    # print(len(extendedRiskyPositions), len(riskyPositions))
    # print("  ", *indexes)
    # for y in range(walls.height):
    #   print(str(y).zfill(2), end=" ")
    #   for x in range(walls.width):
    #     if walls[x][y]:
    #       print("##", end=" ")
    #     elif (x,y) in riskyPositions:
    #       print("xx", end=" ")
    #     else:
    #       print("  ", end=" ")
    #   print()
    # exit(0)
    return riskyPositions

  def getQuickGetawayFeatures(self, minDistanceToExit):
      features = util.Counter()
      features['quickGetaway'] = 2
      features['distanceToExit'] = minDistanceToExit
      return features

  def getFarFromEnemyFeatures(self, action, myPos, foodList, numCarrying, distanceToFood):
    features = util.Counter()
    features['eatFood'] = -len(foodList)
    features['distanceToFood'] = distanceToFood
    if action == Directions.STOP: features['neverStop'] += 99999999999
    if self.onTeamSide(myPos) and myPos not in self.gaps:
      features['onOurSide'] = 2
      self.weights['distanceToExit'] = -10
    elif myPos in self.gaps and numCarrying == 0:
      features['onOurSide'] = 1
    else:
      self.weights['distanceToExit'] = self.defaults['distanceToExit']

    self.weights['distanceToFood'] = self.defaults['distanceToFood'] * 0.5
    return features
  
class DefensiveAgent(DummyAgent):
  def registerInitialState(self, gameState):

    # Built-in register, provides real distancer
    CaptureAgent.registerInitialState(self, gameState)

    # Determine team/side
    self.redTeam = gameState.isOnRedTeam(self.index)
    
    # Indices of each agent
    self.teamIndices = gameState.getRedTeamIndices()
    self.enemyIndices = gameState.getBlueTeamIndices()
    if not self.redTeam:
      self.teamIndices = gameState.getBlueTeamIndices()
      self.enemyIndices = gameState.getRedTeamIndices()

    self.teammateIndex = self.teamIndices[0]
    if self.teammateIndex == self.index:
      self.teammateIndex = self.teamIndices[1]

    # Important positions
    self.startPos = gameState.getAgentPosition(self.index)
    walls = gameState.getWalls()
    self.middleWidth = walls.width / 2    # True middle
    self.middleHeight = walls.height / 2  # True middle
    self.mapWidth = walls.width

    # Construct heat map
    self.map = [ [0]*walls.width for i in range(walls.height)]

    # Find borders
    self.teamBorder = math.floor(self.middleWidth) - 1
    self.enemyBorder = math.floor(self.middleWidth)
    if not gameState.isOnRedTeam(self.index):
      self.teamBorder = math.floor(self.middleWidth)
      self.enemyBorder = math.floor(self.middleWidth) - 1
    
    # Find exit tiles, sorted by distance from center
    if not hasattr(self, 'exits'):
      self.gaps = [] 
      # Determine if each border tile is exit (both sides open)
      for y in range(walls.height):
        if not walls[self.teamBorder][y] and not walls[self.enemyBorder][y]:
          self.gaps.append((self.teamBorder, y))
      
    # Enemy Info
    enemy1Index = self.enemyIndices[0]
    self.enemy1 = {}
    self.enemy1['index'] = enemy1Index
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['startPos'] = gameState.getInitialAgentPosition(self.enemy1['index'])
    self.enemy1['movesSpentAttacking'] = 0
    self.enemy1['vulnerableTurns'] = 0
    self.enemy1['canAttack'] = False
    self.enemy1['spawnToBorder'] = None

    enemy2Index = self.enemyIndices[1]
    self.enemy2 = {}
    self.enemy2['index'] = enemy2Index
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['startPos'] = gameState.getInitialAgentPosition(self.enemy2['index'])
    self.enemy2['movesSpentAttacking'] = 0
    self.enemy2['vulnerableTurns'] = 0
    self.enemy2['canAttack'] = False
    self.enemy2['spawnToBorder'] = None

    # Misc Info
    self.quickGrab = 0
    self.quickGrabPos = None
    self.teamCapsules = gameState.getBlueCapsules()
    self.enemyCapsules = gameState.getRedCapsules()
    if not gameState.isOnRedTeam(self.index):
      self.teamCapsules = gameState.getRedCapsules()
      self.enemyCapsules = gameState.getBlueCapsules()
    self.enemyCapsuleTurns = 0
    self.capsuleBuffer = 3
    self.maxTime = 150 * 4
      
  def chooseAction(self, gameState):
    self.debugClear()
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)
    myPos = gameState.getAgentPosition(self.index)
    movesLeft = gameState.data.timeleft

    # Collect team info
    teammatePos = gameState.getAgentPosition(self.teammateIndex)
    self.myGap = self.findClosestGaps(myPos)[0]

    # Collect enemy info
    enemy1Gaps = self.findClosestGaps(self.enemy1['pos'])
    self.enemy1['gapMain'] = enemy1Gaps[0]
    self.enemy1['gapAlt'] = enemy1Gaps[1]
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['distanceTo'] = self.getMazeDistance(myPos, self.enemy1['pos'])
    self.enemy1['onTeamSide'] = self.onTeamSide(self.enemy1['pos'])
    self.enemy1['numCarrying'] = gameState.getAgentState(self.enemy1['index']).numCarrying
    self.enemy1['vulnerableTurns'] = self.enemy1['vulnerableTurns'] - 1 if self.enemy1['vulnerableTurns'] > 0 else 0
    if self.enemy1['onTeamSide']:
      self.enemy1['canAttack'] = True
    if self.enemy1['spawnToBorder'] == None:
      self.enemy1['spawnToBorder'] = self.enemy1['gapMain'][1]
    enemy2Gaps = self.findClosestGaps(self.enemy2['pos'])
    self.enemy2['gapMain'] = enemy2Gaps[0]
    self.enemy2['gapAlt'] = enemy2Gaps[1]
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['distanceTo'] = self.getMazeDistance(myPos, self.enemy2['pos'])
    self.enemy2['onTeamSide'] = self.onTeamSide(self.enemy2['pos'])
    self.enemy2['numCarrying'] = gameState.getAgentState(self.enemy2['index']).numCarrying
    self.enemy2['vulnerableTurns'] = self.enemy2['vulnerableTurns'] - 1 if self.enemy2['vulnerableTurns'] > 0 else 0
    if self.enemy2['onTeamSide']:
      self.enemy2['canAttack'] = True
    if self.enemy2['spawnToBorder'] == None:
      self.enemy2['spawnToBorder'] = self.enemy2['gapMain'][1]

    if self.enemy1['onTeamSide']:
      self.enemy1['movesSpentAttacking'] += 1
    if self.enemy2['onTeamSide']:
      self.enemy2['movesSpentAttacking'] += 1

    self.mainEnemy = self.assessEnemies(self.enemy1, self.enemy2)
    self.mainEnemyClosestFood = self.getClosestFood(gameState, self.mainEnemy['pos'])[0]
    if self.getMazeDistance(self.mainEnemy['gapMain'][0], self.mainEnemyClosestFood) < self.getMazeDistance(self.mainEnemy['gapAlt'][0], self.mainEnemyClosestFood):
      self.mainEnemyGapPredict = self.mainEnemy['gapMain']
    else:
      self.mainEnemyGapPredict = self.mainEnemy['gapAlt'] 

    # Collect enemy capsule info
    if self.enemyCapsuleTurns > 0:
      self.enemyCapsuleTurns -= 1
    for capsulePos in self.enemyCapsules:
      if capsulePos == self.enemy1['pos'] or capsulePos == self.enemy2['pos']:
        self.enemyCapsuleTurns = 40
        self.enemyCapsules.remove(capsulePos)

    # Collect team capsule info
    for capsulePos in self.teamCapsules:
      if capsulePos == myPos or capsulePos == teammatePos:
        self.enemy1['vulnerableTurns'] = 40
        self.enemy2['vulnerableTurns'] = 40
        self.teamCapsules.remove(capsulePos) 
    #print(self.teamCapsuleTurns)
    #print(self.enemyCapsuleTurns)
    if self.enemy1['pos'] == self.enemy1['startPos'] or (abs(self.enemy1['pos'][0] - self.enemy1['startPos'][0]) + abs(self.enemy1['pos'][1] - self.enemy1['startPos'][1])) or (abs(self.enemy1['pos'][0] - self.enemy2['startPos'][0]) + abs(self.enemy1['pos'][1] - self.enemy2['startPos'][1])) <= 1:
      self.enemy1['vulnerableTurns'] = 0
    if self.enemy2['pos'] == self.enemy2['startPos'] or (abs(self.enemy2['pos'][0] - self.enemy2['startPos'][0]) + abs(self.enemy2['pos'][1] - self.enemy2['startPos'][1])) or (abs(self.enemy2['pos'][0] - self.enemy1['startPos'][0]) + abs(self.enemy2['pos'][1] - self.enemy1['startPos'][1]))<= 1:
      self.enemy2['vulnerableTurns'] = 0

    # Look for quick grabs
    if self.onTeamSide(myPos):
      self.quickGrab = 0
      self.quickGrabPos = None
    if myPos == self.quickGrabPos:
      self.quickGrab = 1
      self.quickGrabPos = None
    if self.quickGrab < 2:
      closestFood = self.getClosestFood(gameState, myPos)
      if closestFood[0] != None:
        self.quickGrabPos = closestFood[0]
        disToFood = closestFood[1]
        disToQuickGrab = disToFood + self.findClosestGaps(self.quickGrabPos)[0][1]

        enemy1DisFromFood = self.getMazeDistance(self.enemy1['pos'], self.quickGrabPos)
        enemy2DisFromFood = self.getMazeDistance(self.enemy2['pos'], self.quickGrabPos)
        # If no time left, return
        if self.myGap[1] + 2 > movesLeft:
          self.quickGrab = 1
          self.quickGrabPos = None
        # If food is reachable without sacrificing defense
        elif (disToFood + 1 < min(enemy1DisFromFood, enemy2DisFromFood)):
          if (((not self.enemy1['canAttack'] and disToQuickGrab + 3 < self.enemy1['distanceTo']) or disToQuickGrab + 3 < self.enemy1['gapMain'][1]) and
              ((not self.enemy2['canAttack'] and disToQuickGrab + 3 < self.enemy2['distanceTo']) or disToQuickGrab + 3 < self.enemy2['gapMain'][1]) and
              (not (not self.enemy1['canAttack'] and not self.enemy1['canAttack']))):
            self.quickGrab = 2
          else:
            self.quickGrabPos = None
        # If enemies vulnerable (or far away), quickGrab
        elif ((self.enemy1['vulnerableTurns'] > self.myGap[1] + self.capsuleBuffer and self.enemy2['vulnerableTurns'] > self.myGap[1] + self.capsuleBuffer and disToQuickGrab + 2 < self.mainEnemy['gapMain'][1]) or
              (self.enemy1['vulnerableTurns'] > self.myGap[1] + self.capsuleBuffer and disToFood + 2 < enemy2DisFromFood and disToQuickGrab < self.enemy2['gapMain'][1]) or
              (disToFood + 2 < enemy1DisFromFood and disToQuickGrab < self.enemy1['gapMain'][1] and self.enemy2['vulnerableTurns'] > self.myGap[1] + self.capsuleBuffer)):
          # But consider if heavyEnemy can cash out
          heaviestEnemy = self.enemyWithMostFood()
          if heaviestEnemy == None or (heaviestEnemy['gapMain'][1] + 2 > self.myGap[1] and not self.onTeamSide(myPos)):
            self.quickGrab = 2
          else:
            self.quickGrabPos = None
        else:
          self.quickGrabPos = None
        '''
        # If team capsuled, quickGrab
        elif (self.teamCapsuleTurns > self.myGap[1] + 5):
          # But consider if heavyEnemy can cash out
          heaviestEnemy = self.enemyWithMostFood()
          if heaviestEnemy == None or heaviestEnemy['gapMain'] + 2 > self.myGap[1]:
            self.quickGrab = 2
        '''
    """if self.quickGrabPos:
      self.debugDraw(self.quickGrabPos, [0,1,0])"""
    
    # Determine heat
    for i in range(len(self.map)):
      for j in range(len(self.map[i])):
        if self.map[i][j] > 0:
          self.map[i][j] -= .5
    self.map[myPos[1]][myPos[0]] += 1
    # Evaluate each action for h value
    #start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    #evalTime = time.time() - start
    #if evalTime > 1:
      #print('eval time for agent %d took too long!: %.4f' % (self.index, evalTime))
      #sys.exit()
    #print('eval time for agent %d: %.4f' % (self.index, evalTime))

    # Find actions of max value
    bestValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    #print(type(self), "Best Actions:", bestActions, "Best Value:", bestValue)
    #print(list(zip(actions,values)))
    return random.choice(bestActions)   # Return random best action
  
  def evaluate(self, gameState, action):
    # Determines value based on features and their weights
    features = None
    if self.quickGrab == 2:
      features = self.getFeatures_QuickGrab(gameState, action)
    else:
      features = self.getFeatures(gameState, action)
    weights = self.getWeights(gameState, action)
    #print("\n","\t"+action + ": " + str(features * weights), "F: " + str(features), "W: " + str(weights), "\n", sep="\n\t")
    return features * weights
  
  def getSuccessor(self, gameState, action):
    """
    Finds the next successor which is a grid position (location tuple).
    """
    successor = gameState.generateSuccessor(self.index, action)
    pos = successor.getAgentState(self.index).getPosition()
    if pos != nearestPoint(pos):
      # Only half a grid position was covered
      return successor.generateSuccessor(self.index, action)
    else:
      return successor
  
  def getFeatures(self, gameState, action):
    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()
    succTeamSide = self.onTeamSide(succPos)
    succGap = self.findClosestGaps(succPos)[0]

    # Enemy Info
    self.enemy1['distanceTo'] =  self.getMazeDistance(succPos, self.enemy1['pos'])
    self.enemy2['distanceTo'] = self.getMazeDistance(succPos, self.enemy2['pos'])
    #self.debugDraw(mainEnemy['pos'], [1,0,0], clear=True)

    # Draw gaps
    # self.debugDraw(self.enemy1['gapMain'][0], [1,0,0])
    # self.debugDraw(self.enemy1['gapAlt'][0], [1,.4,.4])
    # self.debugDraw(self.enemy2['gapMain'][0], [0,1,0])
    # self.debugDraw(self.enemy2['gapAlt'][0], [.6,1,.6])

    ### Features ###
    features = util.Counter()
    features['disFromBorder'] = succGap[1]
    features['onEnemySide'] = not self.onTeamSide(succPos)
    features['mainEnemyRisk'] = self.getMazeDistance(succPos, self.mainEnemy['gapMain'][0])
    features['mainEnemyAltRisk'] = self.getMazeDistance(succPos, self.mainEnemy['gapAlt'][0])
    features['mainEnemyRiskBalance'] = abs(features['mainEnemyRisk'] - features['mainEnemyAltRisk'])
    features['disToOffensiveEnemy'] = self.getMazeDistance(succPos, self.mainEnemy['pos']) if self.onTeamSide(self.mainEnemy['pos']) and action != Directions.STOP else BIG_NUMBER
    features['dontStopOnEnemySide'] = BIG_NUMBER if (not succTeamSide) and action == Directions.STOP else 0
    features['heat'] = self.map[int(succPos[1])][int(succPos[0])] if succTeamSide else 0
    features['willDie'] = 1 if self.enemyCapsuleTurns > 0 and self.adjacentEnemies(succPos) else 0
    features['pop'] = 1 if self.getDisToOffensiveEnemy(gameState, succPos) < 1 else 0
    return features
  
  def getFeatures_QuickGrab(self, gameState, action):
    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()
    succGap = self.findClosestGaps(succPos)[0]

    # Features
    features = util.Counter()
    features['disToFood'] = self.getMazeDistance(succPos, self.quickGrabPos)
    if ((self.enemy1['vulnerableTurns'] > 0) and (self.enemy1['vulnerableTurns'] < succGap[1] + 3) or
        (self.enemy2['vulnerableTurns'] > 0) and (self.enemy2['vulnerableTurns'] < succGap[1] + 3)):
      features['outOfCapsuleTurns'] = succGap[1]
    else:
      features['outOfCapsuleTurns'] = 0
    return features
  
  def getWeights(self, gameState, action):
    weights = {}
    weights['disFromBorder'] = -.5 if not self.quickGrab == 1 else -100        # Prefer close to border, if returning prioritze escaping
    weights['onEnemySide'] = -5           # Discourage entering enemy side when unnecesary
    weights['mainEnemyRisk'] = -1         # Move towards mainEnemy's mainGap
    weights['mainEnemyAltRisk'] = -1      # Move towards mainEnemy's altGap
    # If mainEnemy close to crossing, try to predict based on closest food
    if self.mainEnemyGapPredict[1] < 3:
      if self.mainEnemyGapPredict == self.mainEnemy['gapMain']:
        weights['mainEnemyRisk'] = -3
      else:
        weights['mainEnemyAltRisk'] = -3
    weights['mainEnemyRiskBalance'] = -1  # Prefer in-between of mainEnemy's 2 gaps
    weights['disToOffensiveEnemy'] = -3   # Chase after nearby enemies
    weights['dontStopOnEnemySide'] = -1   # it aint safe out there
    weights['heat'] = -1.5 * min(1, (self.mainEnemy['distanceTo'] - 1) / 5)              # Discourage getting stuck
    weights['willDie'] = -BIG_NUMBER      # Fear death
    weights['pop'] = BIG_NUMBER           # If can eat enemy, do it

    weights['disToFood'] = -1             # For quickgrabbing
    weights['outOfCapsuleTurns'] = -1     # If out of turns, run
    return weights

  def assessEnemies(self, enemy1, enemy2):
    # Add # of carrying food
    # Add comparison of distance from border (if mainEnemy far, guard against close altEnemy)
    mainEnemy = max((enemy1, enemy2), key = lambda enemy : enemy['movesSpentAttacking'])
    # print('Defensive Main enemy:', mainEnemy['index'])
    return mainEnemy
  
  def getClosestFood(self, gameState, pos):
    foodList = self.getFood(gameState).asList()
    if len(foodList) > 0:
      disToFood = BIG_NUMBER
      closestFood = None
      for food in foodList:
        foodDis = self.getMazeDistance(pos, food)
        if foodDis < disToFood:
          disToFood = foodDis
          closestFood = food
    return (closestFood, disToFood)