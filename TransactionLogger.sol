// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract TransactionLogger {
    event TransactionLogged(
        string merchant,
        int256 amount,
        string category,
        string hash,
        uint256 timestamp
    );

    function logTransaction(
        string memory merchant,
        int256 amount,
        string memory category,
        string memory hash
    ) public {
        emit TransactionLogged(merchant, amount, category, hash, block.timestamp);
    }
}
