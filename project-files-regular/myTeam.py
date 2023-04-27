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

BIG_NUMBER = 10000

#################
# Team creation #
#################

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
                    'quickGetaway' : 100 # If can quickly deposit food, do it
                    }

    # Weights that will be returned
    self.weights = self.defaults.copy()

  # Used to DEBUG
  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)

    # Evaluate each action for h value
    #start = time.time()
    #self.debugClear()
    values = [self.evaluate(gameState, a) for a in actions]
    #print('eval time for agent %d: %.4f' % (self.index, time.time() - start))

    # Find actions of max value
    bestValue = max(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    #print(type(self), "Best Actions:", bestActions, "Best Value:", bestValue)
    #print(list(zip(actions,values)))

    move = random.choice(bestActions)

    # ANTI GRIDDY
    if len(self.history) > 5:
      temp = self.history[-5:]
      if temp[0] == temp[2] == temp[4] and temp[1] == temp[3] == move and temp[0] != temp[1]:
        print("NO MORE GRIDDY")
        allActions = sorted(zip(actions, values), key=lambda x: x[1], reverse=True)
        for a in allActions:
          if a[0] != move:
            move = a[0]
            break
        # print("NEW MOVE:", move)
        # exit(0)
        
    self.history.append(move)
    return move # Return random best action

  def getFeatures(self, gameState, action):
    features = util.Counter()
    successor = self.getSuccessor(gameState, action)
    foodList = self.getFood(successor).asList()  
    capsuleList = self.getCapsules(successor)
    enemyList = self.getOpponents(successor)
    myPos = successor.getAgentState(self.index).getPosition()
    numCarrying = gameState.getAgentState(self.index).numCarrying

    self.resetWeights()

    # Stops it from stalling
    if action == Directions.STOP: features['neverStop'] += 99999999999

    # Prioritize not being our side unless its an exit
    if self.onTeamSide(myPos) and myPos not in self.gaps:
      features['onOurSide'] = 2
      self.weights['distanceToExit'] = -10
    elif myPos in self.gaps and numCarrying == 0:
      features['onOurSide'] = 1
    else:
      self.weights['distanceToExit'] = self.defaults['distanceToExit']

    # Prioritize eating food
    features['eatFood'] = -len(foodList)

    # Priortize eating capsules
    features['eatCapsule'] = -len(capsuleList)

    # Compute distance to the nearest capsule
    if len(capsuleList) > 0: 
      minDistance = min([self.getMazeDistance(myPos, capsule) for capsule in capsuleList])
      features['distanceToCapsule'] = minDistance

      # DEBUG draw the closest capsule
      # for capsule in capsuleList:
      #   if self.getMazeDistance(myPos, capsule) == minDistance:
      #     self.debugDraw(capsule, [0,0.8,0.8])

    # Compute distance to the nearest exit
    minDistanceToExit = 1000
    if len(self.gaps) > 0: # This should always be True,  but better safe than sorry
      minDistance = min([self.getMazeDistance(myPos, exit) for exit in self.gaps])
      minDistanceToExit = minDistance
      features['distanceToExit'] += minDistance #* max(features['distanceFromEnemy'], 1)

    # If can make a quick getaway, do it
    currentDistanceFromExit = min([self.getMazeDistance(gameState.getAgentState(self.index).getPosition(), exit) for exit in self.gaps])
    if numCarrying >= 2 and currentDistanceFromExit < 5:
      features = util.Counter()
      features['quickGetaway'] = 2
      features['distanceToExit'] = minDistanceToExit
      return features
    
    # Checks if new position is risky (only on enemy side)
    if myPos in self.risky and not self.onTeamSide(myPos):
      features['risky'] = 1 + features['distanceToExit']
    else: 
      features['risky'] = 0
    
    #DEBUG
    # for risk in self.risky:
    #   if gameState.getAgentState(self.index).getPosition() == risk and not self.onTeamSide(risk):
    #     exit(0)
    #   self.debugDraw(risk, [.2,.3,0])

    # Compute distance to the nearest food
    if len(foodList) > 0: # This should always be True,  but better safe than sorry
      minDistance = min([self.getMazeDistance(myPos, food) for food in foodList])
      features['distanceToFood'] = minDistance

      # DEBUG draw the closest food
      closestFood = None
      for food in foodList:
        if self.getMazeDistance(myPos, food) == minDistance:
          closestFood = food
          #self.debugDraw(food, [0.5,0.5,0])

      # less food available, more likely to be spread apart, so don't worry as much about distance
      self.weights['distanceToFood'] = self.defaults['distanceToFood'] * ((len(foodList) / self.totalFood))
      if self.getScore(successor) > 0: self.weights['distanceToFood'] = -5

    # Increase weight of distance to exit with the more food we have
    self.weights['distanceToExit'] = (-100 if numCarrying > 7 else -(numCarrying * 2))

    # Compute distance to the nearest enemy
    actualDistanceFromEnemy = 1000
    if len(enemyList) > 0:

      minDistance = min([manhattanDistance(myPos, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
      actualDistanceFromEnemy = min([self.getMazeDistance(myPos, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])

      # Keep away if within 5 (Manhattan) units away from enemy (unless actually much further away)
      features['distanceFromEnemy'] = actualDistanceFromEnemy
      if actualDistanceFromEnemy > minDistance + 8: features['distanceFromEnemy'] = 1000

      if actualDistanceFromEnemy < 7:
        self.weights['risky'] = -200
      else:
        self.weights['risky'] = self.defaults['risky']

      # If enemy is FAR away, increase food weight, don't worry about anything else
      if actualDistanceFromEnemy > 15: 
        tempDistance = features['distanceToFood']
        features = util.Counter()
        features['eatFood'] = -len(foodList)
        features['distanceToFood'] = tempDistance
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

      # If enemy is incredibly close, and far from exit, prioritize getting away
      if actualDistanceFromEnemy < 3 and currentDistanceFromExit > 3: self.weights['distanceFromEnemy'] = 300

      # If enemy is incredibly close, and close to exit, prioritize going home
      if actualDistanceFromEnemy <= 3 and currentDistanceFromExit <= 3: 
        self.weights['onOurSide'] = 0
        self.weights['distanceToExit'] = -100000
        return features

      # If enemies are not close to food, priortize it MORE
      minDistanceEnemyFromFood = min([self.getMazeDistance(closestFood, successor.getAgentState(enemy).getPosition()) for enemy in enemyList])
      if minDistanceEnemyFromFood < 10 and actualDistanceFromEnemy > 15 and not self.onTeamSide(myPos):
        features['distanceFromEnemy'] = 1000
        return features
      
      # Don't get KILLED DUMMY
      if actualDistanceFromEnemy == 1: 
        self.weights['distanceFromEnemy'] = -99999
        self.weights['distanceToExit'] = -99999999

      # If eneemy is close, and we are close to capsule, prioritize eating it
      if actualDistanceFromEnemy < 3 and features['distanceToCapsule'] < actualDistanceFromEnemy:
        self.weights['eatCapsule'] = 99999999
      else:
        self.weights['eatCapsule'] = self.defaults['eatCapsule']

    # If we don't have much food, and close to exit (and not close to enemies), don't get capsules
    if (numCarrying < 2 and minDistanceToExit < 3) or (actualDistanceFromEnemy > 5):
      self.weights['distanceToCapsule'] = -500 
      self.weights['eatCapsule'] = -1000
    else:
      self.weights['eatCapsule'] = self.defaults['eatCapsule']

    # If capsule is active
    scaredTime = min([(successor.getAgentState(enemy).scaredTimer) for enemy in enemyList])
    if scaredTime > 0:
      # If we're carrying food, prioritize getting home
      if numCarrying > 4: self.weights['distanceToExit'] = -10000

      # Try not to get other capsules if plenty of time left
      if scaredTime > 15: 
        self.weights['distanceToCapsule'] = 5

      # Chase enemy if they're close AND if timer isn't low
      if scaredTime > 15:
        self.weights['distanceFromEnemy'] = -self.defaults['distanceFromEnemy'] * 60
        if actualDistanceFromEnemy < 2: 
          self.weights['distanceFromEnemy'] = -10000
          features['distanceFromEnemy'] = actualDistanceFromEnemy
      # if currentDistanceFromExit > 15 and actualDistanceFromEnemy > 3:
      #   features['distanceFromEnemy'] = 0  
      else:
        print("RUN FOR YOUR LIFE")
        self.weights['distanceToExit'] = -10000000

    # Reset weights if capsule not active
    else:
      self.weights['distanceToCapsule'] = self.defaults['distanceToCapsule']


    return features

  def getWeights(self, gameState, action):
    return self.weights

  # Reset weights to default
  def resetWeights(self):
    self.weights = self.defaults.copy()

  # finds all positions that have 2 or more walls around them
  def findRiskyPositions(self, gameState):
    walls = gameState.getWalls()
    myPos = gameState.getAgentState(self.index).getPosition()
    indexes = [str(i).zfill(2) for i in range(walls.width)]

    riskyPositions = []

    for x in range(walls.width):
      for y in range(walls.height):
        if walls[x][y]: continue
        surroundingWalls = sum([walls[x+1][y],walls[x-1][y],walls[x][y-1],walls[x][y+1],walls[x+1][y+1],walls[x-1][y-1],walls[x+1][y-1],walls[x-1][y+1]])
        if surroundingWalls >= 6 and ((walls[x+1][y] and walls[x-1][y]) or (walls[x][y-1] and walls[x][y+1])):
          riskyPositions.append((x,y))

    extendedRiskyPositions = []

    for x in range(walls.width):
      for y in range(walls.height):
        if walls[x][y]: continue
        if (x,y) in riskyPositions: continue
        if not ((((x+1,y) in riskyPositions) != ((x-1,y) in riskyPositions)) or (((x,y+1) in riskyPositions) != ((x,y-1) in riskyPositions))): continue
        if ((walls[x+1][y] and walls[x-1][y]) or (walls[x][y-1] and walls[x][y+1])):
          extendedRiskyPositions.append((x,y))
          
    riskyPositions = riskyPositions + extendedRiskyPositions


    #DEBUG
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
    self.enemy1['movesSpentAttacking'] = 0

    enemy2Index = self.enemyIndices[1]
    self.enemy2 = {}
    self.enemy2['index'] = enemy2Index
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['movesSpentAttacking'] = 0

    # Misc Info
    self.quickGrab = 0
    self.quickGrabPos = None
    self.teamCapsules = gameState.getBlueCapsules()
    self.enemyCapsules = gameState.getRedCapsules()
    if not gameState.isOnRedTeam(self.index):
      self.teamCapsules = gameState.getRedCapsules()
      self.enemyCapsules = gameState.getBlueCapsules()
    
    self.enemyCapsuleTurns = 0
    self.teamCapsuleTurns = 0
      
  def chooseAction(self, gameState):
    self.debugClear()
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)
    myPos = gameState.getAgentPosition(self.index)

    # Collect team info
    teammatePos = gameState.getAgentPosition(self.teammateIndex)
    self.myGap = self.findClosestGaps(myPos)[0]

    # Collect enemy info
    enemy1Gaps = self.findClosestGaps(self.enemy1['pos'])
    self.enemy1['gapMain'] = enemy1Gaps[0]
    self.enemy1['gapAlt'] = enemy1Gaps[1]
    self.enemy1['pos'] = gameState.getAgentPosition(self.enemy1['index'])
    self.enemy1['onTeamSide'] = self.onTeamSide(self.enemy1['pos'])
    enemy2Gaps = self.findClosestGaps(self.enemy2['pos'])
    self.enemy2['gapMain'] = enemy2Gaps[0]
    self.enemy2['gapAlt'] = enemy2Gaps[1]
    self.enemy2['pos'] = gameState.getAgentPosition(self.enemy2['index'])
    self.enemy2['onTeamSide'] = self.onTeamSide(self.enemy2['pos'])

    if self.enemy1['onTeamSide']:
      self.enemy1['movesSpentAttacking'] += 1
    if self.enemy2['onTeamSide']:
      self.enemy2['movesSpentAttacking'] += 1

    # Collect enemy capsule info
    if self.enemyCapsuleTurns > 0:
      self.enemyCapsuleTurns -= 1
    for capsulePos in self.enemyCapsules:
      if capsulePos == self.enemy1['pos'] or capsulePos == self.enemy2['pos']:
        self.enemyCapsuleTurns = 40
        self.enemyCapsules.remove(capsulePos)

    # Collect team capsule info
    if self.teamCapsuleTurns > 0:
      self.teamCapsuleTurns -= 1
    for capsulePos in self.teamCapsules:
      if capsulePos == myPos or capsulePos == teammatePos:
        self.teamCapsuleTurns = 40
        self.teamCapsules.remove(capsulePos) 
    #print(self.teamCapsuleTurns)
    #print(self.enemyCapsuleTurns)
    
    # Look for quick grabs
    if self.onTeamSide(myPos):
      self.quickGrab = 0
      self.quickGrabPos = None
    if myPos == self.quickGrabPos:
      self.quickGrab = 1
      self.quickGrabPos = None
    if self.quickGrab < 2:
      foodList = self.getFood(gameState).asList()
      if len(foodList) > 0:
        disToFood = BIG_NUMBER
        for food in foodList:
          foodDis = self.getMazeDistance(myPos, food)
          if foodDis < disToFood:
            disToFood = foodDis
            self.quickGrabPos = food
        disToQuickGrab = disToFood + self.findClosestGaps(self.quickGrabPos)[0][1]
        if (disToFood + 2 < min(self.getMazeDistance(self.enemy1['pos'], self.quickGrabPos), self.getMazeDistance(self.enemy2['pos'], self.quickGrabPos)) and 
            disToQuickGrab < min(self.enemy1['gapMain'][1], self.enemy2['gapMain'][1])):
          self.quickGrab = 2
        else:
            self.quickGrabPos = None
    """if self.quickGrabPos:
      self.debugDraw(self.quickGrabPos, [0,1,0])"""
    
    # Determine heat
    for i in range(len(self.map)):
      for j in range(len(self.map[i])):
        self.map[i][j] -= 1
    self.map[myPos[1]][myPos[0]] += 1

    # Evaluate each action for h value
    #start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    """evalTime = time.time() - start
    if evalTime > 1:
      print('eval time for agent %d took too long!: %.4f' % (self.index, evalTime))
      sys.exit()
    print('eval time for agent %d: %.4f' % (self.index, evalTime))"""

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
    features['disFromBorder'] = self.getMazeDistance(succPos, self.myGap[0])
    features['onEnemySide'] = not self.onTeamSide(succPos)
    features['mainEnemyRisk'] = self.getMazeDistance(succPos, mainEnemy['gapMain'][0])
    features['mainEnemyAltRisk'] = self.getMazeDistance(succPos, mainEnemy['gapAlt'][0])
    features['mainEnemyRiskBalance'] = abs(features['mainEnemyRisk'] - features['mainEnemyAltRisk'])
    features['disToOffensiveEnemy'] = self.getMazeDistance(succPos, mainEnemy['pos']) if self.onTeamSide(mainEnemy['pos']) and action != Directions.STOP else BIG_NUMBER
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

    # Features
    features = util.Counter()
    features['disToFood'] = self.getMazeDistance(succPos, self.quickGrabPos)
    return features
  
  def getWeights(self, gameState, action):
    weights = {}
    weights['disFromBorder'] = -.5 if not self.quickGrab == 1 else -100        # Prefer close to border, if returning prioritze escaping
    weights['onEnemySide'] = -5           # Discourage entering enemy side when unnecesary
    weights['mainEnemyRisk'] = -1         # Move towards mainEnemy's mainGap
    weights['mainEnemyAltRisk'] = -1      # Move towards mainEnemy's altGap
    weights['mainEnemyRiskBalance'] = -1  # Prefer in-between of mainEnemy's 2 gaps
    weights['disToOffensiveEnemy'] = -3   # Chase after nearby enemies
    weights['dontStopOnEnemySide'] = -1   # it aint safe out there
    weights['heat'] = -.5                 # Discourage getting stuck
    weights['willDie'] = -BIG_NUMBER      # Fear death
    weights['pop'] = BIG_NUMBER           # If can eat enemy, do it  
    weights['disToFood'] = -1             # For quickgrabbing
    return weights

  def assessEnemies(self, enemy1, enemy2):
    # Add # of carrying food
    # Add comparison of distance from border (if mainEnemy far, guard against close altEnemy)
    mainEnemy = max((enemy1, enemy2), key = lambda enemy : enemy['movesSpentAttacking'])
    return mainEnemy

  def getDisToOffensiveEnemy(self, gameState, succPos):
    minDis = BIG_NUMBER
    for enemy in self.enemyIndices:
      enemyPos = gameState.getAgentPosition(enemy)
      if self.onTeamSide(enemyPos):
        disToEnemy = self.getMazeDistance(succPos, enemyPos)
        if disToEnemy < minDis:
          minDis = disToEnemy
    return minDis
  
  # Determines if agent is on our team's side
  def onTeamSide(self, pos):
    if self.redTeam: 
      return pos[0] in range(math.floor(self.middleWidth))
    else:
      return pos[0] in range(math.floor(self.middleWidth), self.mapWidth)
    
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
