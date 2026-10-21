# Coverage Record Style Guide

Below are guidelines for writing well-formatted coverage records. Some of these
may seem
random, but we are trying to maximize compatibility for as many Markdown
renderers as possible. Following the instructions below will stop a lot of
common pitfalls.

We provide a linter to help you check your record for Markdown or formatting
issues. Install it with `pip install -r .tiredize/requirements.txt` and run it
from the root of the repository:

```bash
python3 tools/lint_records.py \
  records/<id>/README.md
```

Fix anything it reports before opening a pull request. The linter checks
structure and formatting; run `python3 tools/index.py validate` as well, which
checks the metadata values against this repository's configuration.

## Markdown syntax

The following VSCode extension will report warnings for Markdown syntax related
problems. It is highly recommended to use it and address all warnings as they
come up.

```text
Name: markdownlint
Id: DavidAnson.vscode-markdownlint
Description: Markdown linting and style checking for Visual Studio Code
Version: 0.58.2
Publisher: David Anson
VS Marketplace Link:
https://marketplace.visualstudio.com/items?itemName=DavidAnson.vscode-markdownlint
```

## File and Folder Names

Coverage records go in `README.md` files (which will make GitHub render them
automatically).
The detection logic, which will be automatically pushed to Anvilogic (AVL),
should be in a file named based on the AVL Threat Indicator (TI), such as
`AVL_#######.kql`. Images should be placed in sub-folders called `images`. Files
(other than `README.md` and `AVL_#######.kql`) and directories should be all
lower case and spaces should be replaced with underscores.

**Examples**:

- azure_user_portal.png
- ddm_a_.png
- usb_topology.gif

## Capitalization

Use the original names of products, tools and binaries, preserving the
capitalization. E.g.:

```markdown
# Markdown style guide

`Markdown` is a dead-simple platform for internal engineering documentation.
```

and not

```markdown
# markdown bad style guide example

`markdown` is a dead-simple platform for internal engineering documentation.
```

## Document layout

We have provided a [template] that defines the higher level layout of a coverage
record. The
first and second level headings must be in every coverage record submission.
This helps
ensure consistency across all coverage records. The author has flexibility in
how to use
third and lower level headings to organize their work.

## Line Wrapping

Lines should be wrapped at 80 characters. When GitHub creates a diff between
versions, it will include the entire line in the diff, even if just a few
characters where modified. Long sentences result in large diffs and it's
sometimes difficult to determine what has actually changed. An 80 character line
limit means diffs will be more granular and makes it easy to see what actually
changed.

You can use the following VSCode extension to make this easier:

```text
Name: Rewrap
Id: stkb.rewrap
Description: Hard word wrapping for comments and other text at a given column.
Version: 1.16.3
Publisher: stkb
VS Marketplace Link:
https://marketplace.visualstudio.com/items?itemName=stkb.rewrap
```

Configure the extension with an 80 character line limit and it will
automatically wrap lines as you type. Additionally, you can press `Alt+q` and
the extension will rewrap the full paragraph for you.

There are a few cases where lines over 80 characters are unavoidable: Markdown
tables, code blocks, and long URLs. In these cases, the 80 char line limit is
not enforced. Our linter automatically excludes these cases, so it's easy to
know if they apply.

## Link Format

Below are three examples of Markdown links:

```markdown
- [url text](https://url.com/path)
- [url]
- [any text here][url]

[url]: https://url.com/path
```

The first is an inline link. The second is using a global link, where the link
target is at the bottom of the file to avoid cluttering up the main content. The
third example is using a global link, but with the link's text being
replaced. This allows you to reuse links, while providing context-specific text.

**For submissions for this repository, please use only global links in
paragraphs.** This makes the markdown easier to read for reviews.

## Code Blocks and Backticks

Inline code blocks (in Markdown these are created with backticks: \`thing\`)
should be used to differentiate specific instances of things. For example, SSH
is a pronoun for a service, but `ssh` is the specific binary or process. There
may be instances where pronouns vs inline code blocks are confusing. Choose what
you feel works best and be consistent. If others disagree, it will come up in
the pull request.

Fenced code blocks should be used for console logs, quotes, or source code:

```text
$ cat main.go
package main

func main() {
    println("hello, world!")
}

$ go run ./main.go
hello, world!
```

## Lists

Lists should use `-` as opposed to `*`. This is because `*` is also used for
italics and emphasis which will confuse the linter tool. Make sure to correctly
use whitepace as well. Examples of good and bad lists are below:

### Good List Example

```text
- Bullet 1
  - Sub-bullet 1
- Bullet 2
- Bullet 3
```

### Bad List Example

```text
*  Bullet 1
  *  Sub-bullet 1
*Bullet 2
*   Bullet 3
```

## Ordered Lists

While Markdown will let you created ordered lists using just `1.`, please do not
do that as it's confusing for those reading the raw Markdown files.

### Good Ordered List Example

```text
1. Item 1
2. Item 2
3. Item 3
```

### Bad Ordered List Example

```text
1. Item 1
1. Item 2
1. Item 3
```

[template]: ./TEMPLATE.md
