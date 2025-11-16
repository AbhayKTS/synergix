// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AI Oracle Aggregator
/// @notice Collects oracle assessments, computes consensus, and stores final risk results.
/// @dev This version includes on-chain pending-task queue support for the oracle node.

contract AIOracleAggregator {
    address public owner;

    /// ORACLE REGISTRATION
    mapping(address => bool) public isOracle;
    address[] public oracleList;

    /// CONSENSUS PARAMETERS
    uint256 public minRequiredSubmissions = 3;
    uint8 public quorumPercent = 66; // required % of same category

    /// INTERNAL MAPPINGS
    mapping(address => mapping(address => bool)) private hasSubmitted;

    struct Assessment {
        address oracle;
        uint8 score;      // 0–100
        string ipfsCid;   // evidence
        uint256 timestamp;
    }

    mapping(address => Assessment[]) private assessments;

    struct FinalRisk {
        uint8 aggregatedScore;
        uint8 category;
        string ipfsCid;
        uint256 timestamp;
        uint256 numSubmittingOracles;
    }

    mapping(address => FinalRisk) private finalRisks;
    mapping(address => bool) private isFinalized;

    /// ---------------------------------------------
    /// PENDING TASK SYSTEM  (ADDED FOR ORACLE NODE)
    /// ---------------------------------------------

    address[] private pendingContracts;
    mapping(address => bool) private isPending;

    event TaskRequested(address indexed target, address indexed requester);

    /// ---------------------------------------------
    /// EVENTS
    /// ---------------------------------------------

    event OracleNodeRegistered(address indexed oracle);
    event OracleNodeRemoved(address indexed oracle);
    event AssessmentSubmitted(address indexed target, address indexed oracle, uint8 score, string ipfsCid);
    event RiskAlertIssued(
        address indexed target,
        uint8 aggregatedScore,
        uint8 category,
        string ipfsCid,
        uint256 timestamp,
        uint256 numSubmissions
    );

    /// ---------------------------------------------
    /// MODIFIERS
    /// ---------------------------------------------

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier onlyOracle() {
        require(isOracle[msg.sender], "Only whitelisted oracle");
        _;
    }

    /// ---------------------------------------------
    /// CONSTRUCTOR
    /// ---------------------------------------------

    constructor(address[] memory initialOracles, uint256 _minRequiredSubmissions, uint8 _quorumPercent) {
        owner = msg.sender;

        if (_minRequiredSubmissions > 0) minRequiredSubmissions = _minRequiredSubmissions;
        if (_quorumPercent > 0) {
            require(_quorumPercent <= 100, "quorumPercent max 100");
            quorumPercent = _quorumPercent;
        }

        for (uint256 i = 0; i < initialOracles.length; i++) {
            address o = initialOracles[i];
            if (o != address(0) && !isOracle[o]) {
                isOracle[o] = true;
                oracleList.push(o);
                emit OracleNodeRegistered(o);
            }
        }
    }

    /// ---------------------------------------------
    /// OWNER FUNCTIONS
    /// ---------------------------------------------

    function registerOracle(address oracle) external onlyOwner {
        require(oracle != address(0), "zero address");
        require(!isOracle[oracle], "already oracle");
        isOracle[oracle] = true;
        oracleList.push(oracle);
        emit OracleNodeRegistered(oracle);
    }

    function removeOracle(address oracle) external onlyOwner {
        require(isOracle[oracle], "not oracle");
        isOracle[oracle] = false;

        uint256 len = oracleList.length;
        for (uint256 i = 0; i < len; ++i) {
            if (oracleList[i] == oracle) {
                oracleList[i] = oracleList[len - 1];
                oracleList.pop();
                break;
            }
        }

        emit OracleNodeRemoved(oracle);
    }

    function setConsensusParams(uint256 _minRequiredSubmissions, uint8 _quorumPercent)
        external
        onlyOwner
    {
        require(_minRequiredSubmissions >= 1, "min submissions >=1");
        require(_quorumPercent >= 1 && _quorumPercent <= 100, "quorum 1..100");
        minRequiredSubmissions = _minRequiredSubmissions;
        quorumPercent = _quorumPercent;
    }

    /// ---------------------------------------------
    /// PENDING ASSESSMENTS (ADDED SECTION)
    /// ---------------------------------------------

    /// @notice Add target contract to pending queue
    function requestAssessment(address target) external {
        require(target != address(0), "invalid target");
        require(!isFinalized[target], "already finalized");

        if (!isPending[target]) {
            isPending[target] = true;
            pendingContracts.push(target);
            emit TaskRequested(target, msg.sender);
        }
    }

    function getPendingTasks() external view returns (address[] memory) {
        return pendingContracts;
    }

    function _removePending(address target) internal {
        if (!isPending[target]) return;

        uint256 len = pendingContracts.length;
        for (uint256 i = 0; i < len; ++i) {
            if (pendingContracts[i] == target) {
                pendingContracts[i] = pendingContracts[len - 1];
                pendingContracts.pop();
                isPending[target] = false;
                return;
            }
        }

        isPending[target] = false;
    }

    /// ---------------------------------------------
    /// SUBMISSION LOGIC
    /// ---------------------------------------------

    function submitAssessment(address target, uint8 score, string calldata ipfsCid)
        external
        onlyOracle
    {
        require(target != address(0), "invalid target");
        require(score <= 100, "score 0..100");
        require(!isFinalized[target], "finalized");
        require(!hasSubmitted[target][msg.sender], "already submitted");

        hasSubmitted[target][msg.sender] = true;

        assessments[target].push(
            Assessment({
                oracle: msg.sender,
                score: score,
                ipfsCid: ipfsCid,
                timestamp: block.timestamp
            })
        );

        emit AssessmentSubmitted(target, msg.sender, score, ipfsCid);

        if (assessments[target].length >= minRequiredSubmissions) {
            _tryFinalize(target);
        }
    }

    /// ---------------------------------------------
    /// INTERNAL CONSENSUS
    /// ---------------------------------------------

    function _tryFinalize(address target) internal {
        Assessment[] storage subs = assessments[target];
        uint256 n = subs.length;

        if (n < minRequiredSubmissions) return;

        uint256[3] memory catCount;
        uint256 totalScore = 0;

        for (uint256 i = 0; i < n; ++i) {
            uint8 sc = subs[i].score;
            totalScore += sc;
            uint8 cat = _scoreToCategory(sc);
            catCount[cat]++;
        }

        uint8 winningCat = 0;
        uint256 winningCount = catCount[0];

        for (uint8 c = 1; c < 3; ++c) {
            if (catCount[c] > winningCount) {
                winningCount = catCount[c];
                winningCat = c;
            }
        }

        if (winningCount * 100 >= quorumPercent * n) {
            uint8 avgScore = uint8(totalScore / n);
            string memory chosenCid = _pickCid(subs, winningCat);

            finalRisks[target] = FinalRisk({
                aggregatedScore: avgScore,
                category: winningCat,
                ipfsCid: chosenCid,
                timestamp: block.timestamp,
                numSubmittingOracles: n
            });

            isFinalized[target] = true;

            // NEW: remove from pending once consensus reached
            _removePending(target);

            emit RiskAlertIssued(target, avgScore, winningCat, chosenCid, block.timestamp, n);
        }
    }

    function _scoreToCategory(uint8 score) internal pure returns (uint8) {
        if (score <= 30) return 0;
        if (score < 70) return 1;
        return 2;
    }

    function _pickCid(Assessment[] storage subs, uint8 winningCat)
        internal
        view
        returns (string memory)
    {
        string memory fallbackCid = "";
        string memory firstMatch = "";

        for (uint256 i = 0; i < subs.length; ++i) {
            if (bytes(subs[i].ipfsCid).length > 0 && bytes(fallbackCid).length == 0)
                fallbackCid = subs[i].ipfsCid;

            if (_scoreToCategory(subs[i].score) == winningCat) {
                if (bytes(subs[i].ipfsCid).length > 0) {
                    firstMatch = subs[i].ipfsCid;
                    break;
                }
            }
        }

        if (bytes(firstMatch).length > 0) return firstMatch;
        if (bytes(fallbackCid).length > 0) return fallbackCid;
        return "";
    }

    /// ---------------------------------------------
    /// VIEW FUNCTIONS
    /// ---------------------------------------------

    function getOracleCount() external view returns (uint256) {
        return oracleList.length;
    }

    function getOracleList() external view returns (address[] memory) {
        return oracleList;
    }

    function getAssessmentCount(address target) external view returns (uint256) {
        return assessments[target].length;
    }

    function getAssessment(address target, uint256 index)
        external
        view
        returns (address, uint8, string memory, uint256)
    {
        require(index < assessments[target].length, "index OOB");
        Assessment storage a = assessments[target][index];
        return (a.oracle, a.score, a.ipfsCid, a.timestamp);
    }

    function getFinalRisk(address target)
        external
        view
        returns (uint8, uint8, string memory, uint256, uint256, bool)
    {
        FinalRisk storage r = finalRisks[target];
        if (!isFinalized[target]) return (0, 0, "", 0, 0, false);
        return (r.aggregatedScore, r.category, r.ipfsCid, r.timestamp, r.numSubmittingOracles, true);
    }

    /// ---------------------------------------------
    /// ADMIN UTILS
    /// ---------------------------------------------

    function adminResetTarget(address target) external onlyOwner {
        uint256 len = assessments[target].length;
        for (uint256 i = 0; i < len; ++i) {
            address oracle = assessments[target][i].oracle;
            hasSubmitted[target][oracle] = false;
        }

        delete assessments[target];
        delete finalRisks[target];
        isFinalized[target] = false;

        _removePending(target);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "zero");
        owner = newOwner;
    }
}
