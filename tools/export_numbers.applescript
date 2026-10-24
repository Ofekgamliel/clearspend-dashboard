on run argv
  if (count of argv) is not 2 then error "Expected input and output paths"
  set inputPath to item 1 of argv
  set outputPath to item 2 of argv
  tell application "Numbers"
    activate
    open (POSIX file inputPath as alias)
    delay 2
    set sourceDocument to front document
    export sourceDocument to POSIX file outputPath as Microsoft Excel
    close sourceDocument saving no
  end tell
end run
