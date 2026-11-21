# Weekly builds

One folder per week, named `wNN-short-name` (for example `w01-pass-by-value`, `w02-unique-ptr`).
Each holds the program for that week's Saturday build and a short note on what it shows.

Build and run with sanitizers on:

```bash
g++ -std=c++14 -Wall -Wextra -g -fsanitize=address,undefined main.cpp -o app && ./app
```
