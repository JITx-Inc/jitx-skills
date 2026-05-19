# LB Stanza Syntax Cheatsheet

Surface-syntax reference for LB Stanza. Stanza is AOT-compiled to native code (no JVM).
Verified against Patrick Li's reference-manual.md and by-example.md.

---

## 1. Packages and Imports

A `defpackage` declares a package and may import others. Imports may be prefixed.

```stanza
defpackage mypackage :
   import core
   import collections
   import core with :
      prefix => core-
      prefix(False) => C
```

Visibility modifiers apply to declarations or to a colon-block of declarations.
`public` exposes the binding; `protected` allows reference only via package-qualified
identifiers from other packages.

```stanza
public defn f (x:Int) -> Int : x + 1

public :
   val x = 10
   val y = 20

protected defn g (x) : x
```

---

## 2. Types

Functions, intersections, unions, tuples, parametric, captured, unknown, and `Void`.

```stanza
Int -> Int                ; single-arg function (parens optional)
(Int, Int) -> Int         ; multi-arg function
Seqable & Lengthable      ; intersection
Int | String              ; union
[Int, String]             ; tuple type
Table<Int, String>        ; parametric
?T                        ; captured type argument
?                         ; unknown type
Void                      ; void (function never returns)
```

`?T` is captured from the type of an argument at the call site:

```stanza
defn first<?T> (xs:List<?T>) -> T : head(xs)
```

---

## 3. Declarations

`val` is immutable, `var` is mutable. Types are optional and inferred from RHS.

```stanza
val x:Int = v
val x = v
val [x, [y, z]] = v       ; tuple destructure

var x:Int = v
var x                     ; uninitialized (must be assigned before read)
```

Functions: `defn` for ordinary functions, `defn*` for tail-recursive. Multis and
methods follow the same shape; use `defmethod*` for tail-recursive methods.

```stanza
defn f (x, y) :           ; types default to ? (unknown)
   x + y

defn f (x:Int, y:String) -> Char :
   ...

defn* loop (n:Int) -> False :
   loop(n - 1) when n > 0

defmulti area (s:Shape) -> Double
defmethod area (s:Circle) -> Double :
   PI * radius(s) * radius(s)
```

Types and structs:

```stanza
deftype MyType
deftype MyType <: Collection & Lengthable
deftype MyType<T> <: Collection<T>

defstruct Point :
   x:Int
   y:Int with: (setter => set-y)        ; mutable field
defstruct Tagged<T> <: Parent :
   tag:Symbol
   value:T
with :
   constructor => #Tagged                ; rename generated ctor
   printer => true                        ; auto-print method
```

Variable assignment to a `var` returns false:

```stanza
x = v
```

---

## 4. Expressions and Control Flow

`if`/`else`, `when`, and chained else-if. Without `else`, `if` returns false.

```stanza
if p : a else : b
if p1 : a else if p2 : b else : c
a when p else b           ; sugar for if-expression
return(i) when i*i > 100  ; conditional one-liner
```

`match` dispatches on argument types. Branches without explicit types default to
the input arg types.

```stanza
match(x, y) :
   (x:Int, y:Int) : body0
   (x:Int, y:String) : body1
   (x, y) : body2          ; catch-all
```

`switch` builds an if-chain. Each branch is `f(case)`. Common idiom: equality switch.

```stanza
switch f :
   a : body0
   b : body1
   else : body2

switch {x == _} :
   1 : first()
   2 : second()
   else : default()
```

`let` introduces a new scope. `where` evaluates an expression with auxiliary bindings.

```stanza
let :
   val tmp = compute()
   use(tmp)

result where :
   val result = a + b
```

`for` calls an operating function with an inline lambda. Common ops: `do`, `seq`,
`seq?`, `seq-cat`, `reduce`, `find`, `any?`, `all?`, `none?`, `count`, `filter`,
`map`, `update`.

```stanza
for i in 0 to 10 do :
   println(i)

for (x in xs, y in ys) do :
   println(x => y)

val squares = to-tuple $ for i in 0 to 10 seq :
   i * i

val total = for x in xs reduce(0) :       ; reduce with seed
   _ + x
```

`while` loops while predicate is true.

```stanza
while p :
   body
```

Labeled scopes provide early return. Type parameter optional.

```stanza
label<Int> return :
   for i in 0 to 100 do :
      return(i) when prime?(i)
   fatal("none found")
```

Exceptions: `try`/`catch`/`finally`. `attempt`/`else` is a lighter non-local exit
paired with `fail()`.

```stanza
try :
   body
catch (e:MyExn) :
   handle(e)
finally :
   cleanup()

attempt :
   body                       ; call fail() to abort
else :
   handle-failure()
```

Dynamic variables (let-var) restore on scope exit:

```stanza
let-var x = v :
   body
let-var (x = v1, y = v2) :
   body
```

Generators yield a `Seq<T>`:

```stanza
generate<Int> :
   for i in 1 through 100 do :
      yield(i * i)
   break()                    ; or break(final-value)
```

---

## 5. Functions and Function Sugar

```stanza
fn (x, y) : x + y                                 ; anonymous
fn (x:Int, y:String) -> Char : ...                ; typed
fn* (n) : ...                                     ; tail-recursive

multifn :                                          ; multi-arity anon
   (x) : x + 1
   (x, y) : x + y

{_ + 1}                  ; -> fn (x) : x + 1
{_ * _}                  ; -> fn (x, y) : x * y
{f(_)}                   ; -> fn (x) : f(x)
f{_, y}                  ; -> fn (x) : f(x, y)
{y}                      ; multifn (() : y)((x) : y) -- nullary or unary
f $ x                    ; same as f(x); chains right-to-left
f<Int>(x)                ; polymorphic call
f[i, j]                  ; -> get(f, i, j)
f[i, j] = v              ; -> set(f, i, j, v)
```

---

## 6. Casts and Type Tests

```stanza
x as Int                 ; downcast (fatal if wrong type)
x as Int else fallback   ; downcast with default
x as? Int                ; upcast (returns false if not Int)
x is Type                ; -> True | False
x is-not Type            ; -> True | False
```

---

## 7. Collection / Misc Literals

```stanza
[a, b, c]                ; tuple literal
k => v                   ; KeyValue pair
0 to 10                  ; Range, exclusive end, step 1
0 through 10             ; Range, inclusive end
0 to 10 by 2             ; custom step
0 to false               ; infinite range
`(a 3 c)                 ; literal s-expression (list of symbols / values)
```

`new` creates an object of a `deftype`. With instance methods:

```stanza
new MyType
new MyType :
   defmethod f (this, y:Int) : x + y
```

---

## 8. Common Stdlib (Core Package)

Printing and conversions:

```stanza
print(x)               println(x)             println-all(xs)
write(o, x)            spit(filename, x)      slurp(filename) -> String
to-string(x) -> String to-symbol(x) -> Symbol  name(sym) -> String
gensym()               gensym(name)            id(g:GenSymbol) -> Int
```

Sequence operations (all take a `Seqable`):

```stanza
do(f, xs)              seq(f, xs) -> Seq        seq?(f, xs) -> Seq
seq-cat(f, xs)         filter(pred?, xs)        find(pred?, xs) -> T|False
find!(pred?, xs)       any?(pred?, xs)          all?(pred?, xs)
none?(pred?, xs)       count(pred?, xs)         count(xs)
reduce(f, x0, xs)      reduce(f, xs)            reduce-right(f, xs, xn)
take-n(n, xs)          take-up-to-n(n, xs)      take-while(pred?, xs)
take-until(pred?, xs)  cat(a, b)                cat-all(xss)
zip(xs, ys)            zip(xs, ys, zs)          join(xs, sep)
unique(xs)             contains?(xs, y)         index-of(xs, y)
lookup?(xs, k)         lookup(xs, k)            split(pred?, xs)
fork(xs)               in-reverse(xs)
repeat(x)              repeat(x, n)             repeatedly(f)
```

Conversions:

```stanza
to-tuple(xs)           to-list(xs)              to-vector(xs)
to-array(xs)           to-seq(xs)
```

List / Tuple basics:

```stanza
length(xs)             empty?(xs)               head(l)              tail(l)
cons(x, l)             headn(l, n)              tailn(l, n)          last(l)
but-last(l)            reverse(l)               append(xs, ys)       map(f, xs)
get(t, i)              get(t, r)                List(a, b, c)
```

Maybe:

```stanza
One(x)        None()         value(o:One)        value!(m:Maybe)
value?(m)     value?(m, default)                empty?(m)
```

KeyValue:

```stanza
KeyValue(k, v)    key(kv)    value(kv)
```

Sorting:

```stanza
qsort!(xs)                                ; uses compare
qsort!(xs, less?:(T,T) -> True|False)
qsort!(key:T -> Comparable, xs)
lazy-qsort(xs)                            ; returns sorted Collection
```

System / misc:

```stanza
command-line-arguments() -> Array<String>
file-exists?(path)     resolve-path(path)        delete-file(path)
get-env(name)          set-env(name, val)        call-system(cmd) -> Int
current-time-ms()      current-time-us()
fatal(msg)             throw(e)                  rand()  rand(n)  rand(r)
```

Collections (`collections` package):

```stanza
Vector<T>()           to-vector(xs)             add(v, x)        add-all(v, xs)
pop(v)                peek(v)                   remove(v, i)     clear(v)
remove-when(f, v)     update(f, v)              shorten(v, n)    set-length(v, n, x)

HashTable<K,V>()                               ; key K must be Hashable & Equalable
HashTable<K,V>(default:V)
HashTable<K,V>(hash:K -> Int)
get?(t, k)            get?(t, k, default)       set(t, k, v)
key?(t, k)            keys(t)                   values(t)        remove(t, k)

Queue<T>()            add(q, x)                 pop(q)           peek(q)
```

---

## 9. Strings

```stanza
"hello"                       ; standard string literal (escapes apply)
\<S>literal "quoted" stuff<S> ; raw string; tag may be any token (e.g., \<R>...<R>)
```

Operations:

```stanza
length(s)              empty?(s)              append(a, b)
append-all(strings)    string-join(xs)        string-join(xs, sep)
prefix?(s, p)          suffix?(s, suf)        matches?(s, start, sub)
index-of-char(s, c)    index-of-chars(s, sub) last-index-of-char(s, c)
replace(s, c1, c2)     replace(s, sub1, sub2) split(s, sep) -> Seq<String>
trim(s)                trim(pred?, s)         lower-case(s)  upper-case(s)
to-int(s)              to-double(s)           ; parse, returns False on fail
```

String interpolation uses the `%` operator (returns a `Printable`, not a String):

```stanza
"Hello, %_!" % [name]                    ; %_ next item
"%_ items: %," % [n, items]              ; %, joins Seqable with commas
"%* / %@" % [xs, ys]                     ; %* prints all; %@ pretty-prints all
"100%%"                                   ; %% literal percent
to-string("Hi %_" % [name])              ; convert Printable -> String
```

`%~` pretty-prints next item using `write`.

---

## 10. Numbers

Types: `Byte` (8-bit unsigned), `Int` (32-bit signed), `Long` (64-bit signed),
`Float` (32-bit IEEE), `Double` (64-bit IEEE), `Char` (8-bit ascii).

Literal suffixes: `0Y` (Byte), plain `0` (Int), `0L` (Long), `0.0f` (Float),
`0.0` (Double).

```stanza
+ - * / %                                ; arithmetic (% Int/Long/Byte only)
< <= > >= == !=                          ; comparisons
<< >> >>>                                ; shifts (>>> arithmetic right)
& | ^                                    ; bit-and, bit-or, bit-xor
not x   ~ x   (- x)                      ; complement, bit-not, negate
```

Conversions and bit-ops:

```stanza
to-byte(x)   to-int(x)   to-long(x)   to-float(x)   to-double(x)
bits(d) -> Long          bits(f) -> Int
bits-as-float(i:Int) -> Float
bits-as-double(l:Long) -> Double
abs(x)  max(a,b)  min(a,b)  sum(xs)  product(xs)
ceil-log2(i)  floor-log2(i)  next-pow2(i)  prev-pow2(i)
```

Math (`math` package): `PI`, `PI-F`, `exp`, `log`, `log10`, `pow`, `sin`, `cos`,
`tan`, `asin`, `acos`, `atan`, `atan2`, `sinh`, `cosh`, `tanh`, `ceil`, `floor`,
`round`, `to-radians`, `to-degrees`.

Limits: `INT-MAX`, `INT-MIN`, `LONG-MAX`, `LONG-MIN`, `BYTE-MAX`, `BYTE-MIN`.

---

## 11. Macros and Quasi-Quoting

Backtick produces a literal s-expression. `qquote` substitutes into a template
with `~` (single value) and `~@` (splice list).

```stanza
`(f 3 g)                       ; literal list of (symbol, int, symbol)

val b = 3
qquote(a ~b c)                 ; -> `(a 3 c)

val xs = `(1 2 3)
qquote(a ~@xs c)               ; -> `(a 1 2 3 c)
```

Template engine (`macro-utils` package): `fill-template(template, replacements)`
takes `KeyValue<Symbol, ?>` substitutions; helpers include `splice`, `nested`,
`plural`, `choice`. Reader: `read-file`, `read-all`, `read`. Tokens: `Token`,
`item`, `info`, `unwrap-token`, `unwrap-all`, `tagged-list?`.

---

## 12. LoStanza

LoStanza is a low-level sublanguage with C-like data layout. Functions are
declared with `lostanza defn`; values with `lostanza val`. Primitive types are
lowercase: `byte`, `int`, `long`, `float`, `double`, `ptr<t>`, `ref<T>`.
`ref<T>` is a reference to a Stanza heap object of type `T`.

```stanza
extern generate_fib: (int, int) -> int
extern printf: (ptr<byte>, ? ...) -> int        ; '?' rest = unknown-arity C call
extern malloc: long -> ptr<?>
extern free: ptr<?> -> int
```

A LoStanza function callable from HiStanza must take and return only `ref<T>`:

```stanza
lostanza defn call-fib (b0:ref<Int>, n:ref<Int>) -> ref<Int> :
   val r:int = call-c generate_fib(b0.value, n.value)
   return new Int{r}                            ; LoStanza 'new' boxes a Stanza obj
```

LoStanza types and pointer ops:

```stanza
lostanza deftype Point3D :
   x:float
   y:float
   z:float

lostanza deftype String :
   length: long
   hash: int
   chars: byte ...                              ; trailing variable-length field

lostanza defn try-pointers () -> ref<False> :
   val ints:ptr<int> = call-c malloc(3 * sizeof(int))
   ints[0] = 10                                  ; [] is dereference / index
   val v:int = ints[0]
   call-c free(ints)
   return false
```

`addr(loc)` takes the address of a struct field or array element:

```stanza
lostanza defn greet (option:ref<Int>, name:ref<String>) -> ref<False> :
   val g = call-c choose_greeting(option.value)
   call-c [g](addr(name.chars))                  ; [g] dereferences a function ptr
   return false
```

Calling C uses `call-c f(args...)`. Calling a LoStanza function pointer uses
`call-c [ptr](args...)`. Use `return ...` (LoStanza is statement-oriented).

---

## 13. Compile-Time Flags

Defined externally (compiler `-flag` option) or via `#define`. Conditional
compilation expands to one branch at compile time.

```stanza
#if-defined(DEBUG) :
   println("debug build")
#else :
   ()

#if-not-defined(WINDOWS) :
   posix-init()
```

`#else` is optional; missing branch yields `()`.

---

## Operator Expansion (reference)

```stanza
not x    -> complement(x)
x == y   -> equal?(x, y)        x != y -> not-equal?(x, y)
x < y    -> less?(x, y)         x <= y -> less-eq?(x, y)
x > y    -> greater?(x, y)      x >= y -> greater-eq?(x, y)
x + y    -> plus(x, y)          x - y  -> minus(x, y)
x * y    -> times(x, y)         x / y  -> divide(x, y)
x % y    -> modulo(x, y)
x << y   -> shift-left(x, y)    x >> y -> shift-right(x, y)
x >>> y  -> arithmetic-shift-right(x, y)
x & y    -> bit-and(x, y)       x | y  -> bit-or(x, y)
x ^ y    -> bit-xor(x, y)       (~ x)  -> bit-not(x)
(- x)    -> negate(x)
f $ x    -> f(x)
```
