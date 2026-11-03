package app.projectbots;
public final class PresentationStateTest {
 public static void main(String[] args){
  HistoryLedger history=new HistoryLedger();history.advance(9);history.advance(3);
  if(history.cursor()!=9)throw new AssertionError("late history regressed cursor");
  if(!history.first(4)||history.first(4))throw new AssertionError("duplicate rendered message");
  DraftRevision draft=new DraftRevision();draft.edited();long sent=draft.capture();draft.edited();draft.edited();
  if(draft.unchanged(sent))throw new AssertionError("same-text newer draft cleared by older send");
  if(!draft.unchanged(draft.capture()))throw new AssertionError("unchanged draft not clearable");
  System.out.println("PASS monotonic history/dedup and newer-draft ABA protection");
 }
}
