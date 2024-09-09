-- DROP TABLE IF EXISTS users;
-- DROP TABLE IF EXISTS admin;

CREATE TABLE users (
  userID INTEGER PRIMARY KEY AUTOINCREMENT,
  firstName TEXT,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  driverID INTEGER,
  teamID INTEGER,
  newsletter INTEGER,  -- Represent BOOLEAN as INTEGER (0 = FALSE, 1 = TRUE)
  verified INTEGER,     -- Represent BOOLEAN as INTEGER (0 = FALSE, 1 = TRUE)
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
  PRIMARY KEY (predictionID, driverID),
  FOREIGN KEY (predictionID) REFERENCES predictions(predictionID),
  FOREIGN KEY (driverID) REFERENCES drivers(driverID)
);

CREATE TABLE displayData (
  displayTypeID TEXT,
  driverID INTEGER,
  PRIMARY KEY (displayTypeID, driverID),
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