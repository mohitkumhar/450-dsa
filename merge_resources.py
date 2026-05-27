import json

resources_map = {
  "Array": [
    {"title": "Array Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/array-data-structure/", "type": "article", "difficulty": "Beginner"},
    {"title": "Introduction to Arrays - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/introduction-to-arrays/", "type": "article", "difficulty": "Beginner"},
    {"title": "Array Data Structure | Illustrated - YouTube", "url": "https://www.youtube.com/watch?v=QJNwK2uJyGs", "type": "video", "difficulty": "Beginner"},
    {"title": "Sliding Window Technique - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/window-sliding-technique/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Two Pointer Technique - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/two-pointers-technique/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Kadane's Algorithm - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/largest-sum-contiguous-subarray/", "type": "article", "difficulty": "Intermediate"}
  ],
  "Matrix": [
    {"title": "Matrix Introduction - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/matrix/", "type": "article", "difficulty": "Beginner"},
    {"title": "Spiral Order Matrix Traversal - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/print-a-given-matrix-in-spiral-form/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Matrix Rotation Explained - YouTube", "url": "https://www.youtube.com/watch?v=SA867FvqHdM", "type": "video", "difficulty": "Intermediate"},
    {"title": "Search in Row-wise and Column-wise Sorted Matrix", "url": "https://www.geeksforgeeks.org/search-in-row-wise-and-column-wise-sorted-matrix/", "type": "article", "difficulty": "Intermediate"}
  ],
  "String": [
    {"title": "String Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/string-data-structure/", "type": "article", "difficulty": "Beginner"},
    {"title": "KMP Algorithm for Pattern Searching", "url": "https://www.geeksforgeeks.org/kmp-algorithm-for-pattern-searching/", "type": "article", "difficulty": "Advanced"},
    {"title": "Rabin-Karp Algorithm - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/rabin-karp-algorithm-for-pattern-searching/", "type": "article", "difficulty": "Advanced"},
    {"title": "String Algorithms - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=nV4RnFJdFcg", "type": "video", "difficulty": "Intermediate"},
    {"title": "String Hashing - Codeforces EDU", "url": "https://codeforces.com/edu/course/2/lesson/5", "type": "article", "difficulty": "Intermediate"}
  ],
  "Search & Sort": [
    {"title": "Sorting Algorithms - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/sorting-algorithms/", "type": "article", "difficulty": "Beginner"},
    {"title": "Binary Search - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/binary-search/", "type": "article", "difficulty": "Beginner"},
    {"title": "Binary Search Tutorial - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=W9QJ8HaRvJQ", "type": "video", "difficulty": "Beginner"},
    {"title": "Merge Sort - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/merge-sort/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Quick Sort - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/quick-sort/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Sorting Visualizer", "url": "https://visualgo.net/en/sorting", "type": "tool", "difficulty": "Beginner"}
  ],
  "Linked List": [
    {"title": "Linked List Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/data-structures/linked-list/", "type": "article", "difficulty": "Beginner"},
    {"title": "Linked List Introduction - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=Nq7ok-OyEpg", "type": "video", "difficulty": "Beginner"},
    {"title": "Floyd's Cycle Detection Algorithm", "url": "https://www.geeksforgeeks.org/floyds-cycle-finding-algorithm/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Doubly Linked List - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/doubly-linked-list/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Linked List Visualizer", "url": "https://visualgo.net/en/list", "type": "tool", "difficulty": "Beginner"}
  ],
  "Binary Trees": [
    {"title": "Binary Tree Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/binary-tree-data-structure/", "type": "article", "difficulty": "Beginner"},
    {"title": "Tree Traversals (Inorder, Preorder, Postorder)", "url": "https://www.geeksforgeeks.org/tree-traversals-inorder-preorder-and-postorder/", "type": "article", "difficulty": "Beginner"},
    {"title": "Binary Tree Playlist - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=_ANrF3FJm7I", "type": "video", "difficulty": "Beginner"},
    {"title": "Level Order Traversal (BFS on Tree)", "url": "https://www.geeksforgeeks.org/level-order-tree-traversal/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Lowest Common Ancestor - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/lowest-common-ancestor-binary-tree-set-1/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Binary Tree Visualizer", "url": "https://visualgo.net/en/bst", "type": "tool", "difficulty": "Beginner"}
  ],
  "BST": [
    {"title": "Binary Search Tree - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/binary-search-tree-data-structure/", "type": "article", "difficulty": "Beginner"},
    {"title": "BST Insert, Delete and Search - YouTube", "url": "https://www.youtube.com/watch?v=COZK7NATh4k", "type": "video", "difficulty": "Beginner"},
    {"title": "AVL Tree - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/avl-tree-set-1-insertion/", "type": "article", "difficulty": "Advanced"},
    {"title": "Inorder Successor and Predecessor in BST", "url": "https://www.geeksforgeeks.org/inorder-predecessor-successor-given-key-bst/", "type": "article", "difficulty": "Intermediate"},
    {"title": "BST Visualizer", "url": "https://visualgo.net/en/bst", "type": "tool", "difficulty": "Beginner"}
  ],
  "Greedy": [
    {"title": "Greedy Algorithms - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/greedy-algorithms/", "type": "article", "difficulty": "Beginner"},
    {"title": "Greedy Algorithm Introduction - YouTube", "url": "https://www.youtube.com/watch?v=ARvQcqJ_-NY", "type": "video", "difficulty": "Beginner"},
    {"title": "Activity Selection Problem", "url": "https://www.geeksforgeeks.org/activity-selection-problem-greedy-algo-1/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Huffman Coding Greedy Algorithm", "url": "https://www.geeksforgeeks.org/huffman-coding-greedy-algo-3/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Fractional Knapsack Problem", "url": "https://www.geeksforgeeks.org/fractional-knapsack-problem/", "type": "article", "difficulty": "Intermediate"}
  ],
  "BackTracking": [
    {"title": "Backtracking Introduction - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/backtracking-introduction/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Backtracking Playlist - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=zg5v2rlV1tM", "type": "video", "difficulty": "Intermediate"},
    {"title": "N-Queens Problem - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/n-queen-problem-backtracking-3/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Rat in a Maze - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/rat-in-a-maze-backtracking-2/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Sudoku Solver using Backtracking", "url": "https://www.geeksforgeeks.org/sudoku-backtracking-7/", "type": "article", "difficulty": "Advanced"}
  ],
  "Stacks & Queues": [
    {"title": "Stack Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/stack-data-structure/", "type": "article", "difficulty": "Beginner"},
    {"title": "Queue Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/queue-data-structure/", "type": "article", "difficulty": "Beginner"},
    {"title": "Stack and Queue - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=GYptUgnIM_I", "type": "video", "difficulty": "Beginner"},
    {"title": "Monotonic Stack - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/introduction-to-monotonic-stack-2/", "type": "article", "difficulty": "Intermediate"},
    {"title": "LRU Cache Implementation", "url": "https://www.geeksforgeeks.org/lru-cache-implementation/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Stack & Queue Visualizer", "url": "https://visualgo.net/en/list", "type": "tool", "difficulty": "Beginner"}
  ],
  "Heap": [
    {"title": "Heap Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/heap-data-structure/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Binary Heap - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/binary-heap/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Heap Sort - YouTube", "url": "https://www.youtube.com/watch?v=2DmK_H7IdTo", "type": "video", "difficulty": "Intermediate"},
    {"title": "Priority Queue - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/priority-queue-set-1-introduction/", "type": "article", "difficulty": "Beginner"},
    {"title": "Median in a Stream using Heaps", "url": "https://www.geeksforgeeks.org/median-of-stream-of-integers-running-integers/", "type": "article", "difficulty": "Advanced"},
    {"title": "Heap Visualizer", "url": "https://visualgo.net/en/heap", "type": "tool", "difficulty": "Beginner"}
  ],
  "Graph": [
    {"title": "Graph Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/graph-data-structure-and-algorithms/", "type": "article", "difficulty": "Beginner"},
    {"title": "Graph Series - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=M3_pLsDdeuU", "type": "video", "difficulty": "Beginner"},
    {"title": "BFS for a Graph - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/breadth-first-search-or-bfs-for-a-graph/", "type": "article", "difficulty": "Beginner"},
    {"title": "Dijkstra's Shortest Path Algorithm", "url": "https://www.geeksforgeeks.org/dijkstras-shortest-path-algorithm-greedy-algo-7/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Topological Sort - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/topological-sorting/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Kruskal's MST Algorithm", "url": "https://www.geeksforgeeks.org/kruskals-minimum-spanning-tree-algorithm-greedy-algo-2/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Graph Visualizer", "url": "https://visualgo.net/en/graphds", "type": "tool", "difficulty": "Beginner"}
  ],
  "Trie": [
    {"title": "Trie Data Structure - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/trie-insert-and-search/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Trie Introduction - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=dBGUmUQhjaM", "type": "video", "difficulty": "Intermediate"},
    {"title": "Implement Trie - LeetCode 208", "url": "https://leetcode.com/problems/implement-trie-prefix-tree/", "type": "practice", "difficulty": "Intermediate"},
    {"title": "Trie Delete Operation - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/trie-delete/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Trie Visualizer", "url": "https://visualgo.net/en/suffixtree", "type": "tool", "difficulty": "Intermediate"}
  ],
  "Dynamic Programming": [
    {"title": "Dynamic Programming - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/dynamic-programming/", "type": "article", "difficulty": "Intermediate"},
    {"title": "DP Series - YouTube (take U forward)", "url": "https://www.youtube.com/watch?v=FfXoiwwnxFw", "type": "video", "difficulty": "Intermediate"},
    {"title": "Memoization vs Tabulation", "url": "https://www.geeksforgeeks.org/tabulation-vs-memoization/", "type": "article", "difficulty": "Beginner"},
    {"title": "0/1 Knapsack Problem - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/0-1-knapsack-problem-dp-10/", "type": "article", "difficulty": "Intermediate"},
    {"title": "Longest Common Subsequence - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/longest-common-subsequence-dp-4/", "type": "article", "difficulty": "Intermediate"},
    {"title": "DP on Trees - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/dp-on-trees-set-1/", "type": "article", "difficulty": "Advanced"}
  ],
  "Bit Manipulation": [
    {"title": "Bit Manipulation - GeeksForGeeks", "url": "https://www.geeksforgeeks.org/bits-manipulation-important-tactics/", "type": "article", "difficulty": "Beginner"},
    {"title": "Bit Manipulation Tricks - YouTube", "url": "https://www.youtube.com/watch?v=5rtVTYAk9KQ", "type": "video", "difficulty": "Beginner"},
    {"title": "Bitwise Operators in C/C++", "url": "https://www.geeksforgeeks.org/bitwise-operators-in-c-cpp/", "type": "article", "difficulty": "Beginner"},
    {"title": "Power of Two using Bit Manipulation", "url": "https://www.geeksforgeeks.org/program-to-find-whether-a-given-number-is-power-of-2/", "type": "article", "difficulty": "Beginner"},
    {"title": "Bit Tricks for Competitive Programming", "url": "https://www.geeksforgeeks.org/bit-tricks-for-competitive-programming/", "type": "article", "difficulty": "Intermediate"}
  ]
}

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for topic in data:
    name = topic.get('topicName', '')
    topic['resources'] = resources_map.get(name, [])

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Done! Resources added to all 15 topics.")