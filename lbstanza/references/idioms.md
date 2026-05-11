# LB Stanza Idioms

Patterns of well-written Stanza, distilled from "Stanza By Example" by Patrick S. Li.
Each idiom contrasts a recommended approach with an anti-pattern. The examples are
shaped after passages in the book; verify edge cases against the reference manual.

Stanza compiles natively through a C backend. There is no JVM target.

---

## Multimethod dispatch over match-on-type chains

**Prefer:** Declare a `defmulti` and attach `defmethod`s that can live in any package.
**Over:** A function with a giant `match` over concrete subtypes.
**Why:** Multis are open for extension; downstream code can add methods without editing yours.

```stanza
; preferred
public deftype Shape
public defstruct Circle <: Shape : (radius:Double)
public defstruct Rectangle <: Shape : (w:Double, h:Double)

public defmulti area (s:Shape) -> Double

defmethod area (c:Circle) : PI * radius(c) * radius(c)
defmethod area (r:Rectangle) : w(r) * h(r)

; A user package can extend the protocol without touching the originals.
defmethod area (s:Salinon) :
   val r = outer-radius(s) + inner-radius(s)
   PI * r * r / 4.0
```

```stanza
; avoid
public defn area (s:Shape) -> Double :
   match(s) :
      (c:Circle)    : PI * radius(c) * radius(c)
      (r:Rectangle) : w(r) * h(r)
      ; New shapes require editing this function.
```

---

## Sequences over imperative loops

**Prefer:** Pipeline `seq`/`filter`/`reduce` (or `for ... seq`) over a `Seqable`.
**Over:** Push to a `Vector` inside a `while` loop with manual indexing.
**Why:** Sequence operations are lazy, compose, and read top-down.

```stanza
; preferred
val xs = [1, 3, -2, -7, 3, -8, 9, 10, -3]
val totals = reduce(plus, 0, filter({_ > 0}, xs))
do(println, take-n(3, seq(length, ["Patrick" "Luca" "Emmy"])))
```

```stanza
; avoid
val ys = Vector<Int>()
var i = 0
while i < length(xs) :
   if xs[i] > 0 : add(ys, xs[i])
   i = i + 1
var total = 0
for j in 0 to length(ys) do :
   total = total + ys[j]
```

---

## `for x in xs do` for effects, `for x in xs seq` for values

**Prefer:** `do` when you only need side effects; `seq` to lazily build a `Seq`.
**Over:** Using `do` and pushing into an external `Vector` to "build a result".
**Why:** The `for` construct is sugar for higher-order calls; pick the operating function whose return matches your intent.

```stanza
; preferred — effects
for x in xs do :
   println(x)

; preferred — produce a Seq, lazily
defn cum-sum (xs:Seqable<Int>) :
   var accum = 0
   for x in xs seq :
      accum = accum + x
      accum
```

```stanza
; avoid
val out = Vector<Int>()
var accum = 0
for x in xs do :
   accum = accum + x
   add(out, accum)
```

---

## Immutable structures over mutable ones

**Prefer:** `List`, `Tuple`, and other immutable values when you don't need mutation.
**Over:** Reaching for `Vector` or `HashTable` by reflex.
**Why:** Immutability removes two whole categories of concern: identity and timing.

```stanza
; preferred
val xs = List(1, 2, 3)
val ys = cons(0, xs)        ; xs is unchanged; ys is a new list
val zs = append([42, 43], xs)
```

```stanza
; avoid (when only reading)
val xs = Vector<Int>()
add-all(xs, [1, 2, 3])
; Now every reader has to think about who else might mutate xs.
```

The book observes: with immutable values you no longer have to care *which*
object you have or *when* you operate on it; with mutables, both become load-bearing.

---

## `val` over `var`

**Prefer:** `val` by default; reach for `var` only when rebinding is unavoidable.
**Over:** Declaring everything `var`.
**Why:** Unrebindable bindings are easier to reason about and easier for the compiler to type.

```stanza
; preferred
val r = outer-radius(s) + inner-radius(s)
val area = PI * r * r / 4.0
```

```stanza
; avoid
var r = outer-radius(s) + inner-radius(s)
var area = PI * r * r / 4.0
; r and area are never reassigned — they should be vals.
```

When state is genuinely needed (e.g. a running accumulator inside a loop) `var` is fine:

```stanza
var x = 1
while x < n :
   x = x * 2
```

---

## Labeled scopes for non-local exit

**Prefer:** `label<T>: ...` with a `return` exit function.
**Over:** Boolean flags or sentinel values that thread through nested loops.
**Why:** `label` is the single mechanism Stanza provides for early exit; it composes with loops, recursion, and pulled-out helpers.

```stanza
; preferred
defn bsearch (x:Int, xs:Vector<Int>) :
   label<Int|False> return :
      defn* loop (start:Int, end:Int) :
         if start < end :
            val mid = start + (end - start) / 2
            if x < xs[mid] : loop(start, mid)
            else if x > xs[mid] : loop(mid + 1, end)
            else : return(mid)
      loop(0, length(xs))
```

The exit function is first-class; you can pass it into a helper or even store it
in a variable, and `return(x)` will still unwind to the `label` site.

---

## `attempt`/`fail`/`else` for backtracking

**Prefer:** `attempt`/`else attempt`/`else` for in-program control flow that may need to "try the next thing".
**Over:** Pre-checking with predicate functions that duplicate the parsing/lookup work.
**Why:** `fail` jumps immediately to the next `else`; predicate-then-do double-walks the input.

```stanza
; preferred — s-expression parser
defn parse-symbol () -> Symbol :
   if not letter?(peek(chars)) : fail()
   to-symbol(eat-while(letter?))

defn parse-sequence () -> List :
   eat-whitespace()
   if empty?(chars) : List()
   else :
      attempt :       cons(parse-symbol(),   parse-sequence())
      else attempt :  cons(parse-number(),   parse-sequence())
      else attempt :  cons(parse-list(),     parse-sequence())
      else :          List()
```

```stanza
; avoid
if symbol?(peek-input(chars)) :         ; first walk
   cons(parse-symbol(), parse-sequence())
else if number?(peek-input(chars)) :    ; another walk
   ...
```

---

## `generate` and `yield` for stateful iteration

**Prefer:** `generate<T>:` with `yield(x)` to produce a lazy `Seq<T>`.
**Over:** A hand-rolled `new Seq<T>` with manual `empty?`/`peek`/`next` and explicit state variables.
**Why:** The generator captures the resumption point automatically; the consumer pulls one element at a time without computing the rest.

```stanza
; preferred — depth-first flatten, computed on demand
defn flatten (x:Tuple) -> Seq :
   generate :
      defn loop (x) :
         match(x) :
            (x:Tuple) : do(loop, x)
            (x)       : yield(x)
      loop(x)

; Comparing two trees stops at the first differing element:
all?(equal?, flatten(a), flatten(b))
```

```stanza
; avoid
defn flatten (x:Tuple) -> Vector :
   val v = Vector<?>()
   defn loop (x) :
      match(x) :
         (x:Tuple) : do(loop, x)
         (x)       : add(v, x)
   loop(x)
   v   ; always materializes the full tree, even if the caller only needs one item
```

---

## Coroutines for inverted control

**Prefer:** A `Coroutine<In,Out>` when the *consumer* drives the loop and the producer needs to pause mid-body.
**Over:** Encoding a state machine by hand with a mutable "mode" enum.
**Why:** `suspend`/`resume` express "here is where I am, ask me again later" without flattening the producer's logic.

```stanza
; preferred — key listener that parses words and quoted strings
defn KeyListener (entered: String -> False) -> KeyListener :
   val co = Coroutine<Char,False> $ fn (co, c0) :
      defn next-char () : suspend(co, false)
      val buffer = Vector<Char>()
      defn empty-buffer () :
         entered(string-join(buffer))
         clear(buffer)
      defn* parse (c:Char) :
         if letter?(c) : parse-word(c)
         else if c == '\"' : parse-string(next-char())
         else : parse(next-char())
      ...
   new KeyListener :
      defmethod key-pressed (this, c:Char) :
         resume(co, c)
```

`label`, `attempt`, `try`, and `generate` are all special cases of the coroutine
system; reach for raw coroutines only when none of those fit.

---

## Protocols (multimethod groups) for extensibility

**Prefer:** Declare a `deftype` with a small set of `defmulti`s that constitute its protocol; let downstream packages add subtypes and methods.
**Over:** A closed concrete class hierarchy edited only by the library author.
**Why:** "Fundamental operations" form the contract; "derived operations" build on that contract and work on every implementer for free.

```stanza
; preferred — the Shape protocol
public deftype Shape
public defmulti area (s:Shape) -> Double

; A derived operation that works on any Shape, current or future.
public defn sort-by-area (xs:Vector<Shape>) :
   qsort!(area, xs)

; Downstream package adds a new Shape with no edits to `shape`.
defpackage greek-shapes :
   import core
   import shapes

public defstruct Salinon <: Shape : ...
defmethod area (s:Salinon) : ...
```

A default method, attached to the parent type, gives a fallback when no
specific method matches:

```stanza
defmethod area (s:Shape) :
   println("No area method for %_, returning 0.0." % [s])
   0.0
```

---

## Packages structure surface area; mark exports `public`

**Prefer:** Put related code in a `defpackage`, `import` what you need, and explicitly mark exports as `public`.
**Over:** Splattering every definition into one file or marking everything public "just in case".
**Why:** Defaults are private. Privacy is a contract — outside code *cannot* depend on a private definition, so renaming or removing it is always safe.

```stanza
; preferred
defpackage animals :
   import core

public defstruct Dog : (name:String)
public defstruct Cat : (name:String)

defn dog? (x:Dog|Cat) :          ; private helper
   match(x) :
      (x:Dog) : true
      (x:Cat) : false

public defn sound (x:Dog|Cat) :
   if dog?(x) : "woof"
   else : "meow"
```

For names that *must* be reachable from outside but should not be casually
imported (typical for macro helpers), use `protected` — callers must use the
package-qualified form `animals/sound`.

---

## Parametric functions with captured types

**Prefer:** `?T` capture syntax for type arguments inferable from a collection's element type.
**Over:** Explicit `<T>` arguments at every call site, or worse, falling back to `?` and losing type information at the result.
**Why:** Captured types preserve the input element type all the way through to the result, with no syntactic ceremony at the call site.

```stanza
; preferred — T captured from xs's element type
defn reverse-list<?T> (xs:List<?T>) -> List<T> :
   if empty?(xs) : xs
   else : append(reverse-list(tail(xs)), List(head(xs)))

reverse-list(List(1, 2, 3))                 ; -> List<Int>
reverse-list(List("Timon", "and", "Pumbaa")) ; -> List<String>
```

Capture from the collection, not from a peer argument that should be checked
*against* the collection:

```stanza
; preferred — v must conform to the array's element type
defn store-in-odd-slots<?T> (xs:Array<?T>, v:T) -> False :
   for i in 1 to length(xs) by 2 do :
      xs[i] = v
```

```stanza
; avoid — accepts an arbitrary v and silently widens
defn store-in-odd-slots<?T> (xs:Array<T>, v:?T) -> False :
   ...
```

Multiple capture locations form a union: `<?T>(xs:List<?T>, ys:List<?T>)` called
on `List<Int>` and `List<String>` captures `Int|String`.

---

## Pattern matching with `match` (when it fits)

**Prefer:** `match` for closed sums (a known finite set of subtypes) and for branching on multiple arguments at once.
**Over:** Forcing every dispatch decision through `match`; if extension is the goal, use multimethods.
**Why:** `match` is the right tool when you genuinely *want* the branch list to live in one place — closed unions, cross-product dispatch, and quick local decisions.

```stanza
; preferred — closed local union
defn what-am-i (x:Int|String) :
   match(x) :
      (x:Int)    : println("%_ is an integer." % [x])
      (x:String) : println("%_ is a string."  % [x])

; preferred — dispatch on the cross product of two argument types
defn compare (a:Int|String, b:Int|String) :
   match(a, b) :
      (a:Int,    b:Int)    : a < b
      (a:Int,    b:String) : a < length(b)
      (a:String, b:Int)    : length(a) < b
      (a:String, b:String) : a < b
```

Annotate the union on the parameter (`x:Int|String`) so the compiler enforces
exhaustiveness at the call site rather than crashing with `No matching branch`
at runtime.

---

## Exception handling, sparingly

**Prefer:** `try`/`catch` for inputs you cannot validate cheaply (untrusted strings, I/O, external errors). Use `attempt`/`fail` for in-program control flow you fully control.
**Over:** Throwing exceptions as the default control-flow mechanism, or pre-validating with a predicate that does the same work as the operation.
**Why:** Exceptions cross arbitrary call boundaries and have a runtime cost; `attempt` is local and cheap. Use each for what it is.

```stanza
; preferred — exception at the I/O boundary
defstruct UnclosedParenthesis <: Exception
defmethod print (o:OutputStream, e:UnclosedParenthesis) :
   print(o, "Unclosed opening parenthesis.")

try :
   do(println, parse-sexp(user-input))
catch (e:UnclosedParenthesis) :
   println("You forgot to close a parenthesis. Try again.")
```

```stanza
; preferred — attempt/fail inside the parser itself
defn parse-symbol () -> Symbol :
   if not letter?(peek(chars)) : fail()
   to-symbol(eat-while(letter?))
```

```stanza
; avoid — checking the input as much work as parsing it
if sexp?(user-input) :          ; nearly a full parse
   parse-sexp(user-input)
else :
   ...
```

---

## LoStanza for FFI only

**Prefer:** Keep LoStanza functions thin: declare `extern`, take and return `ref<T>` at the boundary, convert immediately to/from Stanza objects.
**Over:** Spreading LoStanza primitive types (`int`, `double`, `ptr<...>`) through high-level code.
**Why:** A LoStanza function whose argument and return types are all `ref<T>` is callable as a regular Stanza function. Anything else propagates the LoStanza-only restriction outward.

```stanza
; preferred
extern generate_fib: (int, int) -> int

lostanza defn call-fib (b0:ref<Int>, n:ref<Int>) -> ref<Int> :
   val result = call-c generate_fib(b0.value, n.value)
   return new Int{result}

; Stanza side just calls call-fib like any other function:
println(call-fib(1, 10))
```

```stanza
; avoid — leaks LoStanza types into Stanza-callable surface
lostanza defn call-fib (b0:int, n:int) -> int :
   call-c generate_fib(b0, n)
; "LoStanza function ... can only be referred to from LoStanza."
```

Treat LoStanza as a separate language whose only job is to bridge C: convert
`ref<Int>.value -> int` on the way in, and `new Int{result}` on the way out.

---

## Tail-call-optimized recursion over `while` for natural recursion

**Prefer:** `defn*` (or `fn*`) when a function recurses in tail position and you need bounded stack.
**Over:** Mechanically converting every recursive algorithm into a `while` loop.
**Why:** Recursive functions that "stop by default" often read more naturally than `while` loops that "run by default and need a break condition". Stanza only optimizes tail calls in functions explicitly declared with `defn*` / `fn*` / `defmethod*` — the default keeps full stack traces for debugging.

```stanza
; preferred — bounded stack, natural shape
defn sum-of (n:Int) :
   x+sum-of(0, n)

defn* x+sum-of (x:Int, n:Int) :
   if n > 0 : x+sum-of(x + n, n - 1)
   else : x
```

The `while` construct itself desugars to a `defn*` plus a tail call, so this
pattern is *the* loop primitive — `while` is just the most common shape of it.

---

## The `$` and `{...}` shorthands at call sites

**Prefer:** `f $ x` for the rightmost call in a chain, and `{_ + 1}` or `f{x, _}` for tiny anonymous functions.
**Over:** Naming a one-line helper just to pass it once, or piling up parentheses.
**Why:** These are the standard call-site idioms; idiomatic Stanza relies on type inference and rarely annotates anonymous-function arguments.

```stanza
; preferred
do(println, take-n(3, filter({_ > 0}, xs)))

qsort!{xs, _} $ fn (a, b) :
   match(a, b) :
      (a:Int,    b:Int)    : a < b
      (a:String, b:String) : a < b
      (a:Int,    b:String) : a < length(b)
      (a:String, b:Int)    : length(a) < b
```

```stanza
; avoid
defn pos? (x:Int) -> True|False : x > 0
defn cmp (a, b) : ...
qsort!(xs, cmp)
do(println, take-n(3, filter(pos?, xs)))
```
