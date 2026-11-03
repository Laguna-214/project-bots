package app.projectbots;
import java.util.concurrent.*;
public final class SelectionGateTest {
 public static void main(String[] args)throws Exception {
  SelectionGate gate=new SelectionGate();long a=gate.advance();
  CountDownLatch captured=new CountDownLatch(1), release=new CountDownLatch(1);
  FutureTask<Boolean> delayed=new FutureTask<>(()->{captured.countDown();release.await();return gate.current(a);});
  new Thread(delayed).start();captured.await();gate.advance();gate.advance();release.countDown();
  if(delayed.get())throw new AssertionError("ABA stale response accepted");
  long current=gate.advance();if(!gate.current(current))throw new AssertionError("new response rejected");
  gate.advance();if(gate.current(current))throw new AssertionError("logout stale response accepted");
  System.out.println("PASS delayed A→B→A / logout generation invalidation");
 }
}
