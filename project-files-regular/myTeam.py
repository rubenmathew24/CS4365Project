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
from util import nearestPoint, PriorityQueueWithFunction
import math

BIG_NUMBER = 10000

#################
# Team creation #
#################

def createTeam(firstIndex, secondIndex, isRed,
               first = 'DefensiveAgent', second = 'DefensiveAgent'):

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
      self.exits = [] 
      # Determine if each border tile is exit (both sides open)
      for y in range(walls.height):
        if not walls[self.teamBorder][y] and not walls[self.enemyBorder][y]:
          self.exits.append((self.teamBorder, y))
      
      # Sort by distance from center
      #self.exits = sorted(self.exits, key = lambda exit : (abs(self.middleHeight - exit[1])))
      

  def chooseAction(self, gameState):
    # Built-in get possible actions
    actions = gameState.getLegalActions(self.index)

    # Evaluate each action for h value
    start = time.time()
    values = [self.evaluate(gameState, a) for a in actions]
    print('eval time for agent %d: %.4f' % (self.index, time.time() - start))

    # Find actions of max value
    bestValue = min(values)
    bestActions = [a for a, v in zip(actions, values) if v == bestValue]
    return random.choice(bestActions)   # Return random best action
  
  def evaluate(self, gameState, action):
    # Determines value based on features and their weights
    features = self.getFeatures(gameState, action)
    weights = self.getWeights(gameState, action)
    print(f'Agent {self.index} Eval: {features * weights}')
    return features * weights

class DefensiveAgent(DummyAgent):
  
  def getFeatures(self, gameState, action):
    # NO my info Daniel, you dont need that, only deal with succ info

    # Successor info
    succ = self.getSuccessor(gameState, action)
    succState = succ.getAgentState(self.index)
    succPos = succState.getPosition()

    exitsByRisk, entersByRisk = self.assessGapRisk(gameState, self.exits)
    print(exitsByRisk)
    print(entersByRisk)
    mainExit = exitsByRisk[0]
    mainEnter = entersByRisk[0]
    # Find next riskiest exit, don't allow adjacent exits
    exitI = 1
    while(abs(exitsByRisk[exitI][1] - mainExit[0][1]) < 2):
      exitI += 1
    altExit = exitsByRisk[exitI]
    
    enterI = 1
    while(abs(entersByRisk[enterI][1] - mainEnter[0][1]) < 2):
      enterI += 1
    altEnter = entersByRisk[enterI]

    # Draw risky exits
    self.debugDraw(mainExit[0], [1,0,0], clear=True)
    self.debugDraw(altExit[0], [1,.4,.4])
    self.debugDraw(mainEnter[0], [0,1,0])
    self.debugDraw(altEnter[0], [.4,1,.4])

    ### Features ###
    # Defensive
    features = util.Counter()
    features['disFromBorder'] = abs(succPos[0] - self.teamBorder)
    features['exitMainRisk'] = self.distancer.getDistance(succPos, mainExit[0])    # Succ's distance from risky exit (exit an enemy is closest to)
    features['exitAltRisk'] = self.distancer.getDistance(succPos, altExit[0])
    features['enterMainRisk'] = self.distancer.getDistance(succPos, mainEnter[0])
    features['enterAltRisk'] = self.distancer.getDistance(succPos, altEnter[0])
    features['exitRiskBalance'] = abs(features['exitMainRisk'] - features['exitAltRisk'])
    features['disToOffensiveEnemy'] = self.getDisToOffensiveEnemy(gameState, succPos)
    features['onEnemySide'] = not self.inTeamSide(succPos)

    # Offensive
    features['pop'] = 1 if (succPos == gameState.getAgentPosition(self.enemyIndices[0]) or succPos == gameState.getAgentPosition(self.enemyIndices[1])) else 0
    features['disToFood'] = min([self.getMazeDistance(succPos, food) for food in self.getFood(succ).asList()])

    print(features)
    return features
  
  def getWeights(self, gameState, action):
    return {
      'disFromBorder': 1,        # Prefer close to border
      'exitMainRisk': 1,    # Prioritze most threatened exit
      'exitAltRisk': 1,   # Balance out with riskiest, hover in between
      'enterMainRisk': .8,
      'enterAltRisk': .8,
      'disToOffensiveEnemy': 5,  # Chase after nearby enemies
      'onEnemySide': 5,          # Discourage entering enemy side when unnecesary
      #'disToFood': 4,            # Go for nearby food if enemy is far
      'pop': -BIG_NUMBER           # If can eat enemy, do it  
    }

  # Returns list of exits in order of risk (exit that offensive enemy can reach fastest, prefer exits closer to center)
  def assessGapRisk(self, gameState, exits):
    exitDistances = [BIG_NUMBER for exit in exits]   # Init with large value to prefer lowest distances later
    enterDistances = [BIG_NUMBER for exit in exits]   # Init with large value to prefer lowest distances later

    # Only check with offensive enemies
    for enemy in self.enemyIndices:
      enemyPos = gameState.getAgentPosition(enemy)
      # Find distance between enemy and every exit
      for i in range(len(exits)):
        if self.inTeamSide(enemyPos):
          exitDistances[i] = min(exitDistances[i], self.distancer.getDistance(exits[i], enemyPos)) # Store min distance between existing & new to account for multiple offensive
        else:
          enterDistances[i] = min(enterDistances[i], self.distancer.getDistance(exits[i], enemyPos))

    return (sorted(zip(exits, exitDistances), key=lambda pair : (pair[1], abs(self.middleHeight - pair[0][1]))),
            sorted(zip(exits, enterDistances), key=lambda pair : (pair[1], abs(self.middleHeight - pair[0][1]))))
  
  def getClosestOffEnemyPos(self, gameState, succPos):
      closestPos = None
      minDis = BIG_NUMBER
      for enemy in self.enemyIndices:
        enemyPos = gameState.getAgentPosition(enemy)
        if self.inTeamSide(enemyPos):
          if closestPos == None:
            closestPos = enemyPos
            minDis = self.distancer.getDistance(succPos, enemyPos)
          else:
            disToEnemy = self.distancer.getDistance(succPos, enemyPos)
            if disToEnemy < minDis:
              closestPos = enemyPos
              minDis = self.distancer.getDistance(succPos, enemyPos)
      return closestPos

  def getDisToOffensiveEnemy(self, gameState, succPos):
    minDis = BIG_NUMBER
    for enemy in self.enemyIndices:
      enemyPos = gameState.getAgentPosition(enemy)
      if self.inTeamSide(enemyPos):
        disToEnemy = self.distancer.getDistance(succPos, enemyPos)
        if disToEnemy < minDis:
          minDis = disToEnemy
    return minDis


  # Determines if agent is on our team's side
  def inTeamSide(self, pos):
    if self.redTeam: 
      return pos[0] in range(math.floor(self.middleWidth))
    else:
      return pos[0] in range(math.floor(self.middleWidth), self.mapWidth)
    
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

def aStar(gameState, startPos, endPos):
  fringe = PriorityQueueWithFunction(f)
  startNode = {'pos': startPos,
               'ancestor': None,
               'g': 0,
               'h': 0
  }
  fringe.push(startNode)

  expanded = []
  while fringe:
    currentNode = fringe.pop()
  if currentNode['state'] not in expanded:
    expanded.append(currentNode['state'])

    if currentNode['pos'] == endPos:
      path = []
      while (currentNode['ancestor'] is not None):
          path.insert(0, currentNode['pos'])
          currentNode = currentNode['ancestor']
      return path
    


  def f(node):
    return node['g'] + node['h']
