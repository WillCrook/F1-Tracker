-- DROP TABLES IF THEY EXIST
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS admin;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS predictedDriverPos;
DROP TABLE IF EXISTS displayData;
DROP TABLE IF EXISTS drivers;
DROP TABLE IF EXISTS teams;

-- CREATE TABLES
CREATE TABLE users (
  userID INTEGER PRIMARY KEY AUTOINCREMENT,
  firstName TEXT,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  driverID INTEGER,
  teamID INTEGER,
  newsletter INTEGER,  -- Represent BOOLEAN as INTEGER (0 = FALSE, 1 = TRUE)
  verified INTEGER,     -- Represent BOOLEAN as INTEGER (0 = FALSE, 1 = TRUE)
  reset_token VARCHAR(255),
  reset_token_expiry DATETIME,
  FOREIGN KEY (driverID) REFERENCES drivers(driverID),
  FOREIGN KEY (teamID) REFERENCES teams(teamID)
);

CREATE TABLE admin (
  adminID INTEGER PRIMARY KEY AUTOINCREMENT,
  userID INTEGER,
  permissions INTEGER NOT NULL,
  FOREIGN KEY (userID) REFERENCES users(userID)
);

CREATE TABLE predictions (
  predictionID INTEGER PRIMARY KEY AUTOINCREMENT,
  dateOfPrediction DATE,
  afterRace INTEGER,     -- Represent BOOLEAN as INTEGER (0 = FALSE, 1 = TRUE)
  grandPrix TEXT,
  eventPrediction TEXT,
  displayTypeID TEXT,
  FOREIGN KEY (displayTypeID) REFERENCES displayData(displayTypeID)
);

CREATE TABLE predictedDriverPos (
  predictionID INTEGER,
  driverID INTEGER,
  predictedPosition INTEGER,
  actualPosition INTEGER,
  PRIMARY KEY (predictionID, driverID),
  FOREIGN KEY (predictionID) REFERENCES predictions(predictionID),
  FOREIGN KEY (driverID) REFERENCES drivers(driverID)
);

CREATE TABLE displayData (
  displayTypeID TEXT,
  driverID INTEGER,
  grandPrix TEXT,
  views INTEGER, -- Specify the type for 'views' column
  PRIMARY KEY (displayTypeID, grandPrix),
  FOREIGN KEY (driverID) REFERENCES drivers(driverID)
);

CREATE TABLE drivers (
  driverID INTEGER PRIMARY KEY,
  driverName TEXT,
  teamID INTEGER,
  FOREIGN KEY (teamID) REFERENCES teams(teamID)
);

CREATE TABLE teams (
  teamID INTEGER PRIMARY KEY,
  teamName TEXT
);

-- INSERT INITIAL DATA INTO teams TABLE
INSERT INTO teams (teamID, teamName) VALUES
  (1, 'Ferrari'),
  (2, 'Red Bull'),
  (3, 'Mercedes'),
  (4, 'McLaren'),
  (5, 'Aston Martin'),
  (6, 'Alpine'),
  (7, 'AlphaTauri'),
  (8, 'Alfa Romeo'),
  (9, 'Williams'),
  (10, 'Haas');

INSERT INTO drivers (driverID, driverName, teamID) VALUES
  (1, 'Charles Leclerc', 1),
  (2, 'Max Verstappen', 2),
  (3, 'Lewis Hamilton', 3),
  (4, 'Lando Norris', 4),
  (5, 'Fernando Alonso', 5),
  (6, 'Oscar Piastri', 4),
  (7, 'George Russell', 3),
  (8, 'Carlos Sainz', 1),
  (9, 'Sergio Perez', 2),
  (10, 'Nico Hulkenberg', 10),
  (11, 'Daniel Ricciardo', 7),
  (12, 'Yuki Tsunoda', 7),
  (13, 'Kevin Magnussen', 10),
  (14, 'Alex Albon', 9),
  (15, 'Esteban Ocon', 6),
  (16, 'Zhou Guanyu', 8),
  (17, 'Lance Stroll', 5),
  (18, 'Valtteri Bottas', 8),
  (19, 'Franco Colapinto', 9),
  (20, 'Pierre Gasly', 6);
