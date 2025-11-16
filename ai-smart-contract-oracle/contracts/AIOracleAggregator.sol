// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AI Oracle Aggregator
/// @notice Collects signed assessments from whitelisted oracle nodes, computes consensus, and stores a final risk result on-chain.
/// @dev Designed for hackathon / MVP. Owner can register/remove oracle nodes. Consensus threshold is configurable.
contract AIOracleAggregator {
    address public owner;

    /// @dev Oracle registration mapping
    mapping(address => bool) public isOracle;
    address[] public oracleList;

    /// @notice Minimum number of oracle submissions required before evaluating consensus
    uint256 public minRequiredSubmissions = 3;

    /// @notice Percentage (0-100) of agreeing nodes required to accept a final verdict (e.g., 66 -> 66%)
    uint8 public quorumPercent = 66;

    /// @dev Per target contract address => oracle address => whether submitted (prevent duplicates)
    mapping(address => mapping(address => bool)) private hasSubmitted;

    /// @dev Per target contract address => array of submitted assessments
    struct Assessment {
        address oracle;
        uint8 score; // 0..100
        string ipfsCid; // pointer to detailed report
        uint256 timestamp;
    }

    mapping(address => Assessment[]) private assessments;

    /// @dev Final verdict stored when consensus reached
    struct FinalRisk {
        uint8 aggregatedScore; // e.g., average or weighted integer 0..100
        uint8 category; // 0=safe,1=caution,2=danger
        string ipfsCid; // canonical IPFS evidence (optionally chosen from winning submissions)
        uint256 timestamp;
        uint256 numSubmittingOracles;
    }

    mapping(address => FinalRisk) private finalRisks;
    mapping(address => bool) private isFinalized; // whether a contract already has a final verdict

    /// EVENTS
    event OracleNodeRegistered(address indexed oracle);
    event OracleNodeRemoved(address indexed oracle);
    event AssessmentSubmitted(address indexed target, address indexed oracle, uint8 score, string ipfsCid);
    event RiskAlertIssued(address indexed target, uint8 aggregatedScore, uint8 category, string ipfsCid, uint256 timestamp, uint256 numSubmissions);

    /// MODIFIERS
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier onlyOracle() {
        require(isOracle[msg.sender], "Only whitelisted oracle");
        _;
    }

    /// CONSTRUCTOR
    constructor(address[] memory initialOracles, uint256 _minRequiredSubmissions, uint8 _quorumPercent) {
        owner = msg.sender;
        if (_minRequiredSubmissions > 0) {
            minRequiredSubmissions = _minRequiredSubmissions;
        }
        if (_quorumPercent > 0) {
            require(_quorumPercent <= 100, "quorumPercent max 100");
            quorumPercent = _quorumPercent;
        }

        for (uint256 i = 0; i < initialOracles.length; ++i) {
            address o = initialOracles[i];
            if (o != address(0) && !isOracle[o]) {
                isOracle[o] = true;
                oracleList.push(o);
                emit OracleNodeRegistered(o);
            }
        }
    }

    /// OWNER FUNCTIONS

    /// @notice Register a new oracle node (owner-only)
    function registerOracle(address oracle) external onlyOwner {
        require(oracle != address(0), "zero address");
        require(!isOracle[oracle], "already oracle");
        isOracle[oracle] = true;
        oracleList.push(oracle);
        emit OracleNodeRegistered(oracle);
    }

    /// @notice Remove an oracle node (owner-only)
    function removeOracle(address oracle) external onlyOwner {
        require(isOracle[oracle], "not oracle");
        isOracle[oracle] = false;
        // remove from oracleList (gas-ok for small lists; for large lists, prefer different structure)
        for (uint256 i = 0; i < oracleList.length; ++i) {
            if (oracleList[i] == oracle) {
                oracleList[i] = oracleList[oracleList.length - 1];
                oracleList.pop();
                break;
            }
        }
        emit OracleNodeRemoved(oracle);
    }

    /// @notice Update consensus parameters (owner-only)
    function setConsensusParams(uint256 _minRequiredSubmissions, uint8 _quorumPercent) external onlyOwner {
        require(_minRequiredSubmissions >= 1, "min submissions >=1");
        require(_quorumPercent >= 1 && _quorumPercent <= 100, "quorum 1..100");
        minRequiredSubmissions = _minRequiredSubmissions;
        quorumPercent = _quorumPercent;
    }

    /// SUBMISSION LOGIC

    /// @notice Oracles call this to submit their assessment for a target contract
    /// @param target Address of the contract being analyzed
    /// @param score Integer score 0..100 (higher = more risky)
    /// @param ipfsCid IPFS CID pointing to detailed evidence JSON
    function submitAssessment(address target, uint8 score, string calldata ipfsCid) external onlyOracle {
        require(target != address(0), "invalid target");
        require(score <= 100, "score 0..100");
        require(!isFinalized[target], "finalized");

        // prevent same oracle submitting twice for same target
        require(!hasSubmitted[target][msg.sender], "already submitted");
        hasSubmitted[target][msg.sender] = true;

        // record assessment
        assessments[target].push(Assessment({
            oracle: msg.sender,
            score: score,
            ipfsCid: ipfsCid,
            timestamp: block.timestamp
        }));

        emit AssessmentSubmitted(target, msg.sender, score, ipfsCid);

        // if we have enough submissions, try finalize
        if (assessments[target].length >= minRequiredSubmissions) {
            _tryFinalize(target);
        }
    }

    /// INTERNAL: try to compute consensus and finalize if quorum reached
    function _tryFinalize(address target) internal {
        Assessment[] storage subs = assessments[target];
        uint256 n = subs.length;
        if (n < minRequiredSubmissions) return;

        // compute categories counts and average score
        // categories: 0 safe (0..30), 1 caution (31..69), 2 danger (70..100)
        uint256[3] memory catCount;
        uint256 totalScore = 0;

        for (uint256 i = 0; i < n; ++i) {
            uint8 sc = subs[i].score;
            totalScore += sc;
            uint8 cat = _scoreToCategory(sc);
            catCount[cat] += 1;
        }

        // find category with max votes
        uint8 winningCat = 0;
        uint256 winningCount = catCount[0];
        for (uint8 c = 1; c < 3; ++c) {
            if (catCount[c] > winningCount) {
                winningCount = catCount[c];
                winningCat = c;
            }
        }

        // Check quorum: winningCount / n * 100 >= quorumPercent
        // Avoid fractional math by checking: winningCount * 100 >= quorumPercent * n
        if (winningCount * 100 >= uint256(quorumPercent) * n) {
            // consensus reached — compute aggregated score (simple average rounded)
            uint8 avgScore = uint8(totalScore / n);

            // choose ipfsCid: choose the ipfsCid that was most frequent among winning category submissions, fallback to first
            string memory chosenCid = _pickCidForWinningCategory(subs, winningCat);

            // store final risk
            finalRisks[target] = FinalRisk({
                aggregatedScore: avgScore,
                category: winningCat,
                ipfsCid: chosenCid,
                timestamp: block.timestamp,
                numSubmittingOracles: n
            });

            isFinalized[target] = true;

            emit RiskAlertIssued(target, avgScore, winningCat, chosenCid, block.timestamp, n);
        }
        // else do nothing — wait for more submissions
    }

    /// @dev Convert score into category
    function _scoreToCategory(uint8 score) internal pure returns (uint8) {
        if (score <= 30) return 0; // safe
        if (score < 70) return 1;  // caution
        return 2;                  // danger
    }

    /// @dev Pick the IPFS CID most commonly submitted by oracles that voted for winning category.
    function _pickCidForWinningCategory(Assessment[] storage subs, uint8 winningCat) internal view returns (string memory) {
        // We will do a simple first-pass: count most frequent non-empty cid from winning category
        // Because Solidity can't easily map string => uint in storage cheaply, do a two-pass heuristic:
        // 1) look for first non-empty cid from winning category
        // 2) if none, fallback to first submission's cid
        string memory fallbackCid = "";
        string memory firstMatch = "";
        for (uint256 i = 0; i < subs.length; ++i) {
            if (bytes(subs[i].ipfsCid).length > 0 && bytes(fallbackCid).length == 0) {
                fallbackCid = subs[i].ipfsCid;
            }
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

    /// VIEW / GETTER HELPERS

    /// @notice Get number of registered oracle nodes
    function getOracleCount() external view returns (uint256) {
        return oracleList.length;
    }

    /// @notice Get list of registered oracle addresses (careful gas if large)
    function getOracleList() external view returns (address[] memory) {
        return oracleList;
    }

    /// @notice Get number of assessments submitted for a target
    function getAssessmentCount(address target) external view returns (uint256) {
        return assessments[target].length;
    }

    /// @notice Get a single assessment by index for a target
    function getAssessment(address target, uint256 index) external view returns (address oracle, uint8 score, string memory ipfsCid, uint256 timestamp) {
        require(index < assessments[target].length, "index OOB");
        Assessment storage a = assessments[target][index];
        return (a.oracle, a.score, a.ipfsCid, a.timestamp);
    }

    /// @notice Get final risk (if finalized) for a target
    function getFinalRisk(address target) external view returns (uint8 aggregatedScore, uint8 category, string memory ipfsCid, uint256 timestamp, uint256 numSubmittingOracles, bool finalized) {
        FinalRisk storage r = finalRisks[target];
        if (!isFinalized[target]) {
            return (0, 0, "", 0, 0, false);
        }
        return (r.aggregatedScore, r.category, r.ipfsCid, r.timestamp, r.numSubmittingOracles, true);
    }

    /// ADMIN: Allow owner to reset a target (for testing/demo)
    /// @notice Reset assessments and finalization for a target (owner-only). Useful for demos/testnet.
    function adminResetTarget(address target) external onlyOwner {
        // clear submissions
        uint256 len = assessments[target].length;
        for (uint256 i = 0; i < len; ++i) {
            address oracle = assessments[target][i].oracle;
            hasSubmitted[target][oracle] = false;
        }
        delete assessments[target];
        delete finalRisks[target];
        isFinalized[target] = false;
    }

    /// SECURITY: allow owner to transfer ownership
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "zero");
        owner = newOwner;
    }
}
